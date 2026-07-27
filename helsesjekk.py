"""Ukentlig helsesjekk. Kjør mandag morgen - tar 20 sekunder å lese.

Sjekker at skraperne fortsatt treffer (kommunesider og API-er endrer seg over tid),
og oppsummerer nøkkeltall og hva som må fikses:

  - Live-test av byggesak-API (Bergen) og Brreg-API
  - Antall nye leads siste 7 dager
  - Antall aktive betalende kunder (fra Stripe hvis nøkkel finnes, ellers kunder.csv)
  - Utestående i utboksen og eventuelle drift-varsler

Skriver rapport til konsoll og logs/helsesjekk.log, og sender den også på e-post
hvis SMTP er satt opp.

    python helsesjekk.py
"""
import os
from datetime import date, datetime, timezone

import pandas as pd
import requests

import brreg_fetch
import byggesak_fetch
from config import BERGEN_KOMMUNENUMMER, LOG_DIR, PATHS, UTBOKS_DIR, env
from logg import get_logger
from varsling import send_epost

log = get_logger("helsesjekk")


def test_byggesak_api() -> tuple[bool, str]:
    try:
        df = byggesak_fetch.fetch_saker(rows=5)
        if df.empty:
            return False, "Byggesak-API svarte, men ga 0 saker (kilden kan ha endret format)"
        return True, f"Byggesak-API OK ({len(df)} saker i testkall)"
    except Exception as exc:  # noqa: BLE001
        return False, f"Byggesak-API FEILET: {exc}"


def test_brreg_api() -> tuple[bool, str]:
    # Lett enkeltkall (size=1) - tester at endepunktet svarer i forventet form,
    # uten den tunge pagineringen som selve pipelinen gjør.
    try:
        resp = requests.get(brreg_fetch.BRREG_URL, timeout=30, params={
            "naeringskode": "43.210", "kommunenummer": BERGEN_KOMMUNENUMMER, "size": 1})
        resp.raise_for_status()
        data = resp.json()
        if "_embedded" not in data and "page" not in data:
            return False, "Brreg-API svarte, men strukturen er ukjent (kan ha endret format)"
        totalt = data.get("page", {}).get("totalElements", "?")
        return True, f"Brreg-API OK (svarer normalt, {totalt} elektro-treff i Bergen)"
    except Exception as exc:  # noqa: BLE001
        return False, f"Brreg-API FEILET: {exc}"


def nye_leads_7d() -> int:
    if not os.path.exists(PATHS["saker"]):
        return 0
    saker = pd.read_csv(PATHS["saker"])
    if "saksdato" not in saker.columns:
        return 0
    dato = pd.to_datetime(saker["saksdato"], errors="coerce", utc=True)
    grense = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7)
    return int((dato >= grense).sum())


def aktive_kunder() -> tuple[int, str]:
    """Antall betalende kunder. Delegerer til kunder-modulen (Stripe + kunder.csv)."""
    import kunder
    df = kunder.aktive_kunder()
    kilde = "Stripe/kunder.csv" if env("STRIPE_SECRET_KEY") else "kunder.csv"
    return len(df), kilde


def utestaende_utboks() -> int:
    manifest = os.path.join(UTBOKS_DIR, "_manifest.csv")
    if not os.path.exists(manifest):
        return 0
    try:
        return len(pd.read_csv(manifest))
    except Exception:  # noqa: BLE001
        return 0


def bygg_rapport() -> tuple[str, bool]:
    linjer = [f"Byggesaksradar - helsesjekk {date.today().isoformat()}", "=" * 44, ""]
    alt_ok = True

    linjer.append("SKRAPERE (lever kildene fortsatt?)")
    for ok, melding in (test_byggesak_api(), test_brreg_api()):
        linjer.append(f"  {'OK ' if ok else 'FEIL'} - {melding}")
        alt_ok = alt_ok and ok

    antall_kunder, kilde = aktive_kunder()
    mrr = antall_kunder * 99
    linjer += [
        "",
        "NØKKELTALL",
        f"  Nye byggesaker siste 7 dager : {nye_leads_7d()}",
        f"  Aktive kunder ({kilde:<11}): {antall_kunder}  (~{mrr} kr/mnd, mål 500 kr = 6 kunder)",
        f"  E-poster som venter i utboks : {utestaende_utboks()}",
    ]

    # Drift-varsel fra siste selvtest
    alert = os.path.join(LOG_DIR, "selftest_alert.txt")
    linjer += ["", "MÅ FIKSES"]
    if os.path.exists(alert):
        with open(alert, "r", encoding="utf-8") as f:
            linjer.append("  " + f.read().strip().replace("\n", "\n  "))
        alt_ok = False
    if alt_ok:
        linjer.append("  Ingenting - alt ser bra ut.")
    else:
        linjer.append("  Se punktene merket FEIL over.")

    # Faste ukentlige gjøremål
    linjer += [
        "",
        "DINE UKENTLIGE GJØREMÅL",
        "  1. python generate_email_drafts.py --utboks   (lag ferske salgs-e-poster)",
        "  2. python approve_and_send.py --dry-run        (les gjennom)",
        "  3. python approve_and_send.py                  (godkjenn og send)",
    ]
    return "\n".join(linjer), alt_ok


if __name__ == "__main__":
    rapport, alt_ok = bygg_rapport()
    print(rapport)
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(os.path.join(LOG_DIR, "helsesjekk_siste.txt"), "w", encoding="utf-8") as f:
        f.write(rapport + "\n")
    log.info("Helsesjekk kjørt (alt_ok=%s)", alt_ok)
    send_epost(f"Byggesaksradar helsesjekk {date.today().isoformat()}", rapport)
