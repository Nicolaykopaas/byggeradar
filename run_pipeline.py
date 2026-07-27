"""Kjører hele datapipelinen i rekkefølge: Brreg -> byggesaker -> scoring -> utkast.

Kjøres daglig av Task Scheduler / cron. Hvert steg logges, og en statusfil
(data/pipeline_status.json) skrives til slutt slik at selftest.py og
helsesjekk.py kan lese hva som gikk bra/galt uten å tolke loggen.

Brreg-data endrer seg lite fra dag til dag, så bedrifter.csv oppdateres kun hvis
den mangler eller er eldre enn BEDRIFTER_MAKS_ALDER_DAGER. Byggesaker hentes hver gang.

Bruk:
    python run_pipeline.py            # pilot: Bergen (4601)
    python run_pipeline.py 4601 150   # kommunenummer + antall saker
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd

import brreg_fetch
import byggesak_fetch
import compute_scores
import generate_email_drafts
from config import DATA_DIR, BERGEN_KOMMUNENUMMER, PATHS
from logg import get_logger

log = get_logger("pipeline")
STATUS_FIL = os.path.join(DATA_DIR, "pipeline_status.json")
BEDRIFTER_MAKS_ALDER_DAGER = 7


def _bedrifter_er_ferske() -> bool:
    sti = PATHS["bedrifter"]
    if not os.path.exists(sti):
        return False
    alder_dager = (time.time() - os.path.getmtime(sti)) / 86400
    return alder_dager < BEDRIFTER_MAKS_ALDER_DAGER


def _skriv_status(status: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATUS_FIL, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def kjor_pipeline(kommunenummer: str = BERGEN_KOMMUNENUMMER, rows: int = 150) -> dict:
    start = datetime.now(timezone.utc)
    status = {
        "startet": start.isoformat(),
        "kommunenummer": kommunenummer,
        "ok": False,
        "steg": {},
        "tall": {},
        "feil": None,
    }
    os.makedirs(DATA_DIR, exist_ok=True)

    try:
        # 1) Bedrifter fra Brreg (kun ved behov)
        if _bedrifter_er_ferske():
            bedrifter = pd.read_csv(PATHS["bedrifter"], dtype={
                "organisasjonsnummer": str, "nace_kode": str,
                "kommunenummer": str, "postnummer": str,
            })
            log.info("Bruker eksisterende bedrifter.csv (%d rader, fersk nok)", len(bedrifter))
            status["steg"]["brreg"] = "hoppet over (fersk)"
        else:
            log.info("Henter bedrifter fra Brreg for kommune %s ...", kommunenummer)
            bedrifter = brreg_fetch.fetch_bedrifter(kommunenummer)
            bedrifter.to_csv(PATHS["bedrifter"], index=False)
            log.info("Lagret %d bedrifter", len(bedrifter))
            status["steg"]["brreg"] = "ok"
        status["tall"]["bedrifter"] = int(len(bedrifter))

        # 2) Byggesaker
        log.info("Henter byggesaker (rows=%d) ...", rows)
        saker = byggesak_fetch.fetch_saker(rows=rows)
        saker.to_csv(PATHS["saker"], index=False)
        log.info("Lagret %d byggesaker", len(saker))
        status["steg"]["byggesaker"] = "ok"
        status["tall"]["saker"] = int(len(saker))
        if saker.empty:
            raise RuntimeError("Byggesak-API returnerte 0 saker - kilden kan ha endret seg")

        # 3) Scoring
        log.info("Regner matchscore ...")
        # Les tilbake med riktige dtypes (som i compute_scores.__main__)
        saker_typet = pd.read_csv(PATHS["saker"], dtype={
            "kommunenummer": str, "postnummer": str, "sak_id": str})
        bedrifter_typet = pd.read_csv(PATHS["bedrifter"], dtype={
            "organisasjonsnummer": str, "nace_kode": str,
            "kommunenummer": str, "postnummer": str})
        matches = compute_scores.compute_scores(saker_typet, bedrifter_typet)
        matches.to_csv(PATHS["matches"], index=False)
        log.info("Lagret %d matcher", len(matches))
        status["steg"]["scoring"] = "ok"
        status["tall"]["matches"] = int(len(matches))

        # 4) E-postutkast til dashbordet (legacy) - salgs-e-poster lages av
        #    generate_email_drafts.bygg_utboks via approve_and_send-flyten separat.
        try:
            kontaktet = pd.read_csv(PATHS["kontaktet"], dtype={"organisasjonsnummer": str})
        except FileNotFoundError:
            kontaktet = pd.DataFrame(columns=["organisasjonsnummer"])
        antall_utkast = generate_email_drafts.generer_utkast(matches, kontaktet)
        log.info("Genererte %d e-postutkast", antall_utkast)
        status["steg"]["utkast"] = "ok"
        status["tall"]["utkast"] = int(antall_utkast)

        status["ok"] = True
        log.info("Pipeline fullført OK")
    except Exception as exc:  # noqa: BLE001 - vi vil logge alt og signalisere feil
        log.exception("Pipeline feilet: %s", exc)
        status["feil"] = f"{type(exc).__name__}: {exc}"

    status["ferdig"] = datetime.now(timezone.utc).isoformat()
    _skriv_status(status)
    return status


if __name__ == "__main__":
    kommune = sys.argv[1] if len(sys.argv) > 1 else BERGEN_KOMMUNENUMMER
    antall = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    resultat = kjor_pipeline(kommune, antall)
    sys.exit(0 if resultat["ok"] else 1)
