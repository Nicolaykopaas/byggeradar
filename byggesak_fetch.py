"""Henter nye byggesaker fra Bergen kommunes saksinnsyn-API.

Verifisert: robots.txt for bergen.kommune.no blokkerer kun
/innsynplanogbyggesak/api/fil/* og /innsynplanogbyggesak/api/saksgang -
selve søke-API-et (/api/saker) er ikke omfattet.

Trondheim (trondheim.innsynsportal.no) og Oslo PBE
(innsyn.pbe.oslo.kommune.no) er UTELUKKET - begge har robots.txt
"Disallow: /" og skal ikke skrapes.

VIKTIG: API-responsen inneholder "tiltakshaver" (navnet på privatpersonen
som søker). Dette er en personopplysning og skal ALDRI lagres eller
videreformidles - kun bedriftsdata fra Brreg skal brukes i matching og
utsending. Feltet leses aldri ut i denne filen.

Output: data/saker.csv
"""
import re
import time
from datetime import datetime, timezone

import requests
import pandas as pd

BERGEN_KOMMUNENUMMER = "4601"
BERGEN_API_URL = "https://www.bergen.kommune.no/innsynplanogbyggesak/api/saker"
BERGEN_SAK_URL_MAL = "https://www.bergen.kommune.no/omkommunen/offentlig-innsyn/innsynplanogbyggesak/saksinnsyn/sak/{saksnr}"


def _hent_postnummer(adresse_liste) -> str | None:
    """Adressefeltet fra API-et er på formen 'Gateveien 1, 5230 Paradis'."""
    if not adresse_liste:
        return None
    match = re.search(r"(\d{4})\s+\S", adresse_liste[0])
    return match.group(1) if match else None


def _hent_gateadresse(adresse_liste) -> str | None:
    if not adresse_liste:
        return None
    return adresse_liste[0].split(",")[0].strip()


def fetch_saker(rows: int = 100, sleep_s: float = 0.3) -> pd.DataFrame:
    """Hent de `rows` sist innkomne byggesakene fra Bergen, nyest først."""
    params = {
        "tekst": "BYGG",  # matcher saksnr-prefiks BYGG-YYYY/NNNN, dvs. alle byggesaker
        "start": 0,
        "rows": rows,
        "orderBy": "saksdato",
        "asc": "false",
    }
    resp = requests.get(BERGEN_API_URL, params=params, timeout=20)
    resp.raise_for_status()
    time.sleep(sleep_s)

    items = resp.json().get("items", [])
    rader = []
    for sak in items:
        saksnr = sak.get("saksnr")
        saksdato_ms = sak.get("saksdato")
        saksdato = (
            datetime.fromtimestamp(saksdato_ms / 1000, tz=timezone.utc).date().isoformat()
            if saksdato_ms else None
        )
        adresse_liste = sak.get("adresse") or []

        rader.append({
            "sak_id": saksnr,
            "kommunenummer": BERGEN_KOMMUNENUMMER,
            "postnummer": _hent_postnummer(adresse_liste),
            "adresse": _hent_gateadresse(adresse_liste),
            "saksdato": saksdato,
            "sakstype": sak.get("tittel"),
            "kilde_url": BERGEN_SAK_URL_MAL.format(saksnr=saksnr) if saksnr else None,
        })

    return pd.DataFrame(rader)


if __name__ == "__main__":
    import sys
    rows = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    df = fetch_saker(rows=rows)
    df.to_csv("data/saker.csv", index=False)
    print(f"Lagret {len(df)} byggesaker til data/saker.csv")
