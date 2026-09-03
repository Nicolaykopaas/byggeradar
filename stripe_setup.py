"""Oppretter produkt, pris (99 kr/mnd) og en Stripe Payment Link, via requests.

Vi bruker Stripe sitt REST-API direkte med `requests` (ingen `stripe`-pakke) for å
holde oss til avhengighetsregelen i CLAUDE.md. Du limer inn din egen hemmelige
nøkkel i .env:

    STRIPE_SECRET_KEY=sk_live_...    # eller sk_test_... mens du tester

Kjøring er idempotent: URL-en lagres i data/stripe_link.txt og gjenbrukes.
Kjør på nytt med --force for å lage en ny lenke.

    python stripe_setup.py           # opprett (eller vis eksisterende) lenke
    python stripe_setup.py --force   # tving ny lenke

Alternativt: lag en Payment Link manuelt i Stripe-dashbordet og lim inn
STRIPE_PAYMENT_LINK=https://buy.stripe.com/... i .env. Da trenger du ikke dette
scriptet i det hele tatt, build_landing.py bruker den lenken direkte.
"""
import os
import sys

import requests

from config import DATA_DIR, env
from logg import get_logger

log = get_logger("stripe")
STRIPE_API = "https://api.stripe.com/v1"
LINK_FIL = os.path.join(DATA_DIR, "stripe_link.txt")

PRODUKT_NAVN = "Byggesaksradar, ukentlige leads"
PRODUKT_BESKRIVELSE = "Ukentlig e-post med nye byggesaker i ditt område og din bransje."
PRIS_ORE = 9900          # 99,00 kr
VALUTA = "nok"


def _post(sti: str, nokkel: str, data: dict) -> dict:
    resp = requests.post(f"{STRIPE_API}/{sti}", auth=(nokkel, ""), data=data, timeout=30)
    if resp.status_code >= 400:
        raise RuntimeError(f"Stripe {sti} feilet ({resp.status_code}): {resp.text}")
    return resp.json()


def opprett_payment_link(nokkel: str) -> str:
    produkt = _post("products", nokkel, {
        "name": PRODUKT_NAVN,
        "description": PRODUKT_BESKRIVELSE,
    })
    log.info("Opprettet produkt %s", produkt["id"])

    pris = _post("prices", nokkel, {
        "product": produkt["id"],
        "unit_amount": PRIS_ORE,
        "currency": VALUTA,
        "recurring[interval]": "month",
    })
    log.info("Opprettet pris %s (%d øre/mnd)", pris["id"], PRIS_ORE)

    lenke = _post("payment_links", nokkel, {
        "line_items[0][price]": pris["id"],
        "line_items[0][quantity]": 1,
    })
    log.info("Opprettet payment link %s", lenke["id"])
    return lenke["url"]


def hent_eller_opprett(force: bool = False) -> str:
    # 1) Manuelt satt lenke i .env vinner alltid
    manuell = env("STRIPE_PAYMENT_LINK")
    if manuell and not force:
        log.info("Bruker STRIPE_PAYMENT_LINK fra .env")
        return manuell

    # 2) Tidligere opprettet lenke
    if os.path.exists(LINK_FIL) and not force:
        with open(LINK_FIL, "r", encoding="utf-8") as f:
            url = f.read().strip()
        if url:
            log.info("Bruker eksisterende lenke fra %s", LINK_FIL)
            return url

    # 3) Opprett ny via API
    nokkel = env("STRIPE_SECRET_KEY")
    if not nokkel:
        raise SystemExit(
            "Mangler STRIPE_SECRET_KEY i .env. Lim inn din hemmelige Stripe-nøkkel, "
            "eller sett STRIPE_PAYMENT_LINK direkte hvis du lagde lenken i dashbordet."
        )
    url = opprett_payment_link(nokkel)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LINK_FIL, "w", encoding="utf-8") as f:
        f.write(url + "\n")
    log.info("Lagret lenke til %s", LINK_FIL)
    return url


if __name__ == "__main__":
    force = "--force" in sys.argv
    url = hent_eller_opprett(force=force)
    print(f"Betalingslenke: {url}")
