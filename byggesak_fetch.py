"""Henter nye byggesaker fra Bergen kommunes saksinnsyn-API.

Verifisert: robots.txt for bergen.kommune.no blokkerer kun
/innsynplanogbyggesak/api/fil/* og /innsynplanogbyggesak/api/saksgang -
selve søke-API-et (/api/saker) er ikke omfattet.

Trondheim (trondheim.innsynsportal.no) og Oslo PBE
(innsyn.pbe.oslo.kommune.no) er UTELUKKET - begge har robots.txt
"Disallow: /" og skal ikke skrapes.

VIKTIG (personvern): "tiltakshaver" (navnet på privatpersonen som søker) er en
personopplysning og leses ALDRI ut / lagres aldri. Feltet "soker" (ansvarlig
søker) leses KUN for å utlede én boolean - `profesjonell_soker` (ser søkeren ut
som et foretak, ja/nei) - som brukes til å anslå om jobben trolig alt er tildelt.
Selve navnet lagres aldri; kun ja/nei-flagget havner i saker.csv. Dette er avklart
og ønsket (jf. brukerbeslutning), og holder oss innenfor personvernregelen.

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

# Kommunens API timer av og til ut. Ett feilet kall skal ikke rive ned pipelinen.
REQUEST_TIMEOUT = 30


def _get_med_retry(url, params, timeout=REQUEST_TIMEOUT, forsok=3):
    """requests.get med eksponentiell backoff (1s, 2s, 4s) ved nettverksfeil.

    Prøver på nytt ved requests.exceptions.RequestException (timeout/connection).
    Hever siste feil hvis alle forsøk feiler.
    """
    siste_feil = None
    for n in range(forsok):
        try:
            return requests.get(url, params=params, timeout=timeout)
        except requests.exceptions.RequestException as feil:
            siste_feil = feil
            if n < forsok - 1:
                time.sleep(2 ** n)  # 1s, 2s, 4s, ...
    raise siste_feil


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


# Foretaks-kjennetegn: selskapsformer (hele ord) + typiske bransjeord i firmanavn.
_FORETAK = re.compile(
    r"\b(AS|ASA|ANS|DA|BA|SA|NUF|KS|ENK)\b|BYGG|ENTREPREN|EIENDOM|PROSJEKT|"
    r"UTVIKLING|HOLDING|GRUPPEN|INVEST|ANLEGG|MASKIN|ARKITEKT|BOLIG|TOMTE", re.I)


def _er_profesjonell_soker(soker) -> bool:
    """Leser KUN for å utlede ja/nei - navnet lagres aldri (se personvern-notat øverst).

    True hvis ansvarlig søker ser ut som et foretak (AS o.l.), False hvis det ser ut
    som en privatperson eller mangler. Brukes til å anslå «ledig vs tatt».
    """
    if not soker:
        return False
    tekst = " ".join(soker) if isinstance(soker, list) else str(soker)
    return bool(_FORETAK.search(tekst))


def fetch_saker(rows: int = 100, sleep_s: float = 0.3) -> pd.DataFrame:
    """Hent de `rows` sist innkomne byggesakene fra Bergen, nyest først."""
    params = {
        "tekst": "BYGG",  # matcher saksnr-prefiks BYGG-YYYY/NNNN, dvs. alle byggesaker
        "start": 0,
        "rows": rows,
        "orderBy": "saksdato",
        "asc": "false",
    }
    resp = _get_med_retry(BERGEN_API_URL, params)
    resp.raise_for_status()
    time.sleep(sleep_s)

    items = resp.json().get("items", [])
    rader = []
    for sak in items:
        saksnr = sak.get("saksnr")
        # Fritekstsøket "BYGG" drar også inn henvendelser (HENV-), klager (KLAGE-) og
        # tilsyn (TILSYN-) fordi ordet "bygg" står i tittelen. Det er ikke reelle
        # byggetillatelser og gir verdiløse leads - behold kun ekte byggesaker (BYGG-).
        if not (saksnr and str(saksnr).startswith("BYGG-")):
            continue
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
            "status": sak.get("status"),  # f.eks. "Under behandling" / "Avsluttet"
            # KUN boolean - navnet på søker lagres aldri (personvern, se toppen):
            "profesjonell_soker": _er_profesjonell_soker(sak.get("soker")),
            "kilde_url": BERGEN_SAK_URL_MAL.format(saksnr=saksnr) if saksnr else None,
        })

    return pd.DataFrame(rader)


if __name__ == "__main__":
    import sys
    rows = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    df = fetch_saker(rows=rows)
    df.to_csv("data/saker.csv", index=False)
    print(f"Lagret {len(df)} byggesaker til data/saker.csv")
