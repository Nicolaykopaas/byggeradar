"""Bygger landing/index.html fra malen ved å sette inn betalingslenke + eksempel-lead.

Den ferdige index.html spores ikke av git (den inneholder din betalingslenke) og
kan lastes gratis opp på GitHub Pages, Netlify Drop eller Cloudflare Pages.

    python build_landing.py

Krever at du enten har satt STRIPE_PAYMENT_LINK i .env, eller kjørt stripe_setup.py.
Eksempel-lead hentes fra data/matches.csv hvis den finnes (ellers en placeholder).
"""
import os
from datetime import date

import pandas as pd

from config import BASE_DIR, PATHS, env
from leads import velg_eksempel_lead
from logg import get_logger
from stripe_setup import hent_eller_opprett

log = get_logger("landing")

MAL = os.path.join(BASE_DIR, "landing", "index.template.html")
UT = os.path.join(BASE_DIR, "landing", "index.html")
PRIS_KR = "99"


def _hent_eksempel() -> dict:
    try:
        matches = pd.read_csv(PATHS["matches"], dtype={"organisasjonsnummer": str, "sak_id": str})
        lead = velg_eksempel_lead(matches)
        if lead:
            return lead
    except FileNotFoundError:
        pass
    log.info("Ingen matches.csv - bruker placeholder-eksempel")
    return {"sakstype": "Tilbygg til enebolig", "omrade": "Sentrumsnært område",
            "bransje": "Snekkerarbeid/tømrer", "score": 90, "dato": ""}


def bygg() -> str:
    # Betalingslenke: prøv .env/lagret/API, men ikke stopp bygget hvis den mangler
    try:
        lenke = hent_eller_opprett()
    except SystemExit as exc:
        log.warning("Betalingslenke ikke klar (%s). Bruker plassholder '#'.", exc)
        lenke = "#"

    eksempel = _hent_eksempel()
    with open(MAL, "r", encoding="utf-8") as f:
        html = f.read()

    erstatt = {
        "{{BETALINGSLENKE}}": lenke,
        "{{EKSEMPEL_SAKSTYPE}}": str(eksempel["sakstype"]),
        "{{EKSEMPEL_OMRADE}}": str(eksempel["omrade"]),
        "{{EKSEMPEL_BRANSJE}}": str(eksempel["bransje"]),
        "{{EKSEMPEL_SCORE}}": str(eksempel["score"]),
        "{{PRIS}}": PRIS_KR,
        "{{GENERERT}}": date.today().isoformat(),
    }
    for nokkel, verdi in erstatt.items():
        html = html.replace(nokkel, verdi)

    with open(UT, "w", encoding="utf-8") as f:
        f.write(html)
    log.info("Skrev %s (betalingslenke: %s)", UT, lenke)
    return UT


if __name__ == "__main__":
    sti = bygg()
    print(f"Bygget landingsside: {sti}")
    print("Last den opp gratis på f.eks. GitHub Pages eller Netlify Drop (se README).")
