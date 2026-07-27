"""HOVEDLEVERINGEN: ukentlige byggesak-leads til betalende kunder.

Dette er selve produktet kundene betaler 99 kr/mnd for. Kjores ukentlig (kan
schedulerst). For hver aktive kunde plukkes ukens NYE, relevante byggesaker fra
data/matches.csv + data/saker.csv, og det bygges EN ryddig norsk e-post.

Fordi dette er en BETALT, samtykket leveranse er full adresse OK her (i motsetning
til de kalde salgs-e-postene i generate_email_drafts.py, som anonymiserer).

To moduser:
    python send_kunde_leads.py --dry-run   # skriv e-postene til data/kunde_utboks/, send ingenting
    python send_kunde_leads.py             # send via SMTP, logg og arkiver

Dedupe: samme (kunde, sak_id) sendes aldri to ganger (data/kunde_sendt.csv).
Kunder uten nye leads denne uka hoppes over (ingen tom e-post).
"""
import os
import re
import sys
from datetime import date, datetime, timedelta

import pandas as pd

from config import KUNDE_SENDT_DIR, KUNDE_UTBOKS_DIR, PATHS, env
from kunder import aktive_kunder
from leads import rensk_sakstype
from logg import get_logger
from varsling import send_epost

log = get_logger("kundelevering")

TOPP_N = 10          # maks antall leads per e-post
DAGER_TILBAKE = 7    # "ukens" saker = saksdato siste 7 dager


# --- Innlesing -------------------------------------------------------------
def _les_matches() -> pd.DataFrame:
    try:
        return pd.read_csv(PATHS["matches"], dtype={"sak_id": str, "organisasjonsnummer": str})
    except FileNotFoundError:
        return pd.DataFrame()


def _les_saker() -> pd.DataFrame:
    try:
        return pd.read_csv(PATHS["saker"], dtype=str).fillna("")
    except FileNotFoundError:
        return pd.DataFrame()


def _les_kunde_sendt() -> pd.DataFrame:
    try:
        return pd.read_csv(PATHS["kunde_sendt"], dtype=str).fillna("")
    except FileNotFoundError:
        return pd.DataFrame(columns=["epost", "sak_id", "dato"])


def _logg_sendt(rader: list):
    """Legg til (epost, sak_id, dato)-rader i data/kunde_sendt.csv."""
    if not rader:
        return
    ny = pd.DataFrame(rader, columns=["epost", "sak_id", "dato"])
    finnes = os.path.exists(PATHS["kunde_sendt"])
    os.makedirs(os.path.dirname(PATHS["kunde_sendt"]), exist_ok=True)
    ny.to_csv(PATHS["kunde_sendt"], mode="a", header=not finnes, index=False)


# --- Utvalg per kunde ------------------------------------------------------
def _bransjesett(kunde) -> set:
    return {b.strip().lower() for b in str(kunde.get("bransjer", "")).split(";") if b.strip()}


def _min_score(kunde) -> float:
    try:
        return float(str(kunde.get("min_score", "0")).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def finn_leads_for_kunde(kunde, matches: pd.DataFrame, saker_indeks: dict,
                         terskel_dato) -> pd.DataFrame:
    """Returner de unike, relevante, ferske sakene for en kunde (en rad per sak_id).

    Filter: bransje i kundens bransjer (hvis satt), score >= min_score,
    postnummer starter paa kundens prefiks (hvis satt), kommunenummer matcher
    (hvis satt), og saksdato innenfor siste DAGER_TILBAKE dager.
    """
    if matches.empty:
        return matches

    df = matches.copy()

    # Score-terskel.
    df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0)
    df = df[df["score"] >= _min_score(kunde)]

    # Bransjefilter (tom = alle).
    onskede = _bransjesett(kunde)
    if onskede:
        df = df[df["bransje"].astype(str).str.strip().str.lower().isin(onskede)]
    if df.empty:
        return df

    # Berik med saker-data (postnummer, kilde_url, full adresse, kommunenummer).
    df["_postnummer"] = df["sak_id"].map(lambda s: saker_indeks.get(s, {}).get("postnummer", ""))
    df["_kilde_url"] = df["sak_id"].map(lambda s: saker_indeks.get(s, {}).get("kilde_url", ""))
    df["_adresse"] = df["sak_id"].map(lambda s: saker_indeks.get(s, {}).get("adresse", ""))
    df["_kommune"] = df["sak_id"].map(lambda s: saker_indeks.get(s, {}).get("kommunenummer", ""))

    # Kommunefilter (hvis satt paa kunden og kjent for saken).
    kommune = str(kunde.get("kommunenummer", "")).strip()
    if kommune:
        df = df[(df["_kommune"] == kommune) | (df["_kommune"] == "")]

    # Postnummer-prefiks (hvis satt). Saker uten postnummer faller ut naar prefiks kreves.
    prefiks = str(kunde.get("postnummer_prefiks", "")).strip()
    if prefiks:
        df = df[df["_postnummer"].astype(str).str.startswith(prefiks)]

    # Ferske saker: saksdato siste DAGER_TILBAKE dager.
    df["_dato"] = pd.to_datetime(df["saksdato"], errors="coerce")
    df = df[df["_dato"].notna() & (df["_dato"] >= terskel_dato)]
    if df.empty:
        return df

    # En rad per sak: behold hoyest score (og ferskest) per sak_id.
    df = (df.sort_values(["score", "_dato"], ascending=[False, False])
            .drop_duplicates(subset="sak_id", keep="first"))
    return df


# --- E-postbygging ---------------------------------------------------------
def _hilsen(kunde) -> str:
    navn = str(kunde.get("navn", "")).strip()
    return f"Hei {navn}," if navn else "Hei,"


def bygg_epost(kunde, leads: pd.DataFrame) -> tuple:
    """Bygg (emne, tekst) for en kunde med gitte leads (allerede sortert/toppet)."""
    antall = len(leads)
    emne = f"Byggesaksradar: {antall} nye byggesak{'er' if antall != 1 else ''} denne uka"

    linjer = [
        _hilsen(kunde),
        "",
        f"Her er ukens nye byggesaker som passer ditt omraade og fag ({antall} stk):",
        "",
    ]
    for i, (_, r) in enumerate(leads.iterrows(), start=1):
        sakstype = rensk_sakstype(r.get("sakstype"))
        adresse = str(r.get("_adresse") or r.get("sak_adresse") or "").strip()
        postnr = str(r.get("_postnummer") or "").strip()
        omrade = ", ".join(x for x in (adresse, postnr) if x) or "Bergen kommune"
        dato = str(r.get("saksdato") or "").strip()
        url = str(r.get("_kilde_url") or "").strip()

        linjer.append(f"{i}. {sakstype}")
        linjer.append(f"   Omraade:  {omrade}")
        if dato:
            linjer.append(f"   Saksdato: {dato}")
        if url:
            linjer.append(f"   Se saken: {url}")
        linjer.append("")

    linjer += [
        "Lykke til! Ta kontakt med tiltakshaver tidlig - foer konkurrentene.",
        "",
        "-- ",
        "Byggesaksradar (99 kr/mnd)",
        f'Vil du melde deg av? Svar "stopp" paa denne e-posten, saa stopper vi utsendingen til {kunde.get("epost", "")}.',
    ]
    return emne, "\n".join(linjer)


def _trygg_filnavn(tekst: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", str(tekst))[:80]


def _skriv_epostfil(katalog: str, epost: str, emne: str, tekst: str) -> str:
    os.makedirs(katalog, exist_ok=True)
    filnavn = f"{_trygg_filnavn(epost)}_{date.today().isoformat()}.txt"
    sti = os.path.join(katalog, filnavn)
    with open(sti, "w", encoding="utf-8") as f:
        f.write(f"To: {epost}\nSubject: {emne}\n\n{tekst}\n")
    return sti


# --- Hovedlokke ------------------------------------------------------------
def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    dry_run = "--dry-run" in argv

    kunder = aktive_kunder()
    if kunder.empty:
        print("Ingen aktive kunder. Legg til med: python sett_kunde.py legg-til ...")
        log.info("Ingen aktive kunder - ingenting aa levere.")
        return 0

    matches = _les_matches()
    saker = _les_saker()
    if matches.empty:
        print(f"Fant ingen matches ({PATHS['matches']}). Kjor pipelinen forst.")
        log.warning("matches.csv mangler eller er tom.")
        return 1

    # Indeks sak_id -> saksfelter for rask oppslag.
    saker_indeks = {}
    if not saker.empty:
        for _, s in saker.iterrows():
            saker_indeks[str(s.get("sak_id"))] = {
                "postnummer": str(s.get("postnummer", "")).strip(),
                "kilde_url": str(s.get("kilde_url", "")).strip(),
                "adresse": str(s.get("adresse", "")).strip(),
                "kommunenummer": str(s.get("kommunenummer", "")).strip(),
            }

    terskel_dato = pd.Timestamp(datetime.now().date() - timedelta(days=DAGER_TILBAKE))
    sendt_logg = _les_kunde_sendt()

    modus = "[TORRKJORING] " if dry_run else ""
    print(f"{modus}Leverer ukens leads til {len(kunder)} aktiv(e) kunde(r) "
          f"(saker fra og med {terskel_dato.date()}):\n")

    nye_sendt_rader = []
    antall_epost = antall_hoppet = 0

    for _, kunde in kunder.iterrows():
        epost = str(kunde.get("epost", "")).strip()
        if not epost:
            continue

        leads = finn_leads_for_kunde(kunde, matches, saker_indeks, terskel_dato)

        # Dedupe: fjern saker denne kunden allerede har faatt.
        if not leads.empty and not sendt_logg.empty:
            alt_sendt = set(
                sendt_logg.loc[sendt_logg["epost"].str.strip().str.lower() == epost.lower(),
                               "sak_id"].astype(str)
            )
            if alt_sendt:
                leads = leads[~leads["sak_id"].astype(str).isin(alt_sendt)]

        if leads.empty:
            antall_hoppet += 1
            print(f"  - {epost}: ingen nye leads denne uka - hopper over.")
            log.info("Ingen nye leads for %s - hopper over.", epost)
            continue

        leads = leads.sort_values(["score", "_dato"], ascending=[False, False]).head(TOPP_N)
        emne, tekst = bygg_epost(kunde, leads)

        if dry_run:
            sti = _skriv_epostfil(KUNDE_UTBOKS_DIR, epost, emne, tekst)
            print(f"  - {epost}: {len(leads)} lead(s) -> {sti}")
            antall_epost += 1
            continue

        if send_epost(emne, tekst, til=epost):
            _skriv_epostfil(KUNDE_SENDT_DIR, epost, emne, tekst)
            idag = date.today().isoformat()
            for sak_id in leads["sak_id"].astype(str):
                nye_sendt_rader.append({"epost": epost, "sak_id": sak_id, "dato": idag})
            print(f"  - {epost}: sendte {len(leads)} lead(s).")
            log.info("Sendte %d leads til %s.", len(leads), epost)
            antall_epost += 1
        else:
            print(f"  - {epost}: SENDING FEILET (sjekk SMTP i .env). Logger ikke som sendt.")
            log.error("Sending til %s feilet - hopper over logging.", epost)

    if not dry_run:
        _logg_sendt(nye_sendt_rader)

    print(f"\n{modus}Ferdig: {antall_epost} e-post(er), {antall_hoppet} kunde(r) uten nye leads.")
    if dry_run:
        print(f"Torrkjoring - ingenting sendt. Se e-postene i {KUNDE_UTBOKS_DIR}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
