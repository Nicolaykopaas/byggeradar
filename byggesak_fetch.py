"""Henter nye byggesaker fra en kommunes offentlige postliste (RSS).

Kun kilder der robots.txt tillater automatisert henting brukes - se KOMMUNER
for hvilke kommuner som er godkjent og hvorfor. Output: data/saker.csv

NB: Trondheim (trondheim.innsynsportal.no) og Oslo PBE (innsyn.pbe.oslo.kommune.no)
er UTELUKKET - begge har robots.txt "Disallow: /" og skal ikke skrapes.
"""
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import requests
import pandas as pd

# Nøkkelord som identifiserer byggesaker i postlistens tittel/beskrivelse
BYGGESAK_NOKKELORD = [
    "tillatelse til tiltak", "byggesøknad", "søknad om tiltak",
    "igangsettingstillatelse", "bruksendring", "riving", "nybygg",
    "tilbygg", "påbygg", "ferdigattest", "rammetillatelse",
]

# Kommuner godkjent for henting: RSS-URL og kommunenummer må fylles inn
# etter at datakilde er verifisert (robots.txt tillater, RSS finnes).
KOMMUNER = {
    # "eksempel": {"kommunenummer": "0000", "rss_url": "https://..."},
}


def er_byggesak(tekst: str) -> bool:
    tekst_lower = (tekst or "").lower()
    return any(nokkelord in tekst_lower for nokkelord in BYGGESAK_NOKKELORD)


def hent_adresse_fra_tittel(tittel: str) -> str:
    """Beste-forsøk-uttrekk av adresse fra fritekst-tittel. Returnerer hele
    tittelen hvis ikke noe adresse-lignende mønster finnes."""
    match = re.search(r"([A-ZÆØÅa-zæøå .]+\d+[A-Za-z]?)(,|\s-\s|$)", tittel)
    return match.group(1).strip() if match else tittel


def fetch_saker(kommune_key: str, sleep_s: float = 0.5) -> pd.DataFrame:
    if kommune_key not in KOMMUNER:
        raise ValueError(
            f"Ukjent kommune '{kommune_key}'. Legg til RSS-URL og kommunenummer i KOMMUNER "
            f"- kun kommuner der robots.txt tillater henting skal legges til."
        )
    conf = KOMMUNER[kommune_key]

    resp = requests.get(conf["rss_url"], timeout=20)
    resp.raise_for_status()
    time.sleep(sleep_s)

    root = ET.fromstring(resp.content)
    rader = []
    for item in root.iter("item"):
        tittel = (item.findtext("title") or "").strip()
        beskrivelse = (item.findtext("description") or "").strip()
        if not er_byggesak(f"{tittel} {beskrivelse}"):
            continue

        lenke = item.findtext("link") or ""
        pub_dato = item.findtext("pubDate") or ""

        rader.append({
            "sak_id": lenke or f"{kommune_key}-{tittel[:40]}",
            "kommunenummer": conf["kommunenummer"],
            "postnummer": None,
            "adresse": hent_adresse_fra_tittel(tittel),
            "saksdato": pub_dato,
            "sakstype": tittel,
            "kilde_url": lenke,
        })

    return pd.DataFrame(rader)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2 or sys.argv[1] not in KOMMUNER:
        print(f"Bruk: python byggesak_fetch.py <kommune>. Tilgjengelige: {list(KOMMUNER.keys())}")
        print("Ingen kommune er lagt til KOMMUNER ennå - se README for status.")
        sys.exit(1)

    df = fetch_saker(sys.argv[1])
    df.to_csv("data/saker.csv", index=False)
    print(f"Lagret {len(df)} byggesaker til data/saker.csv")
