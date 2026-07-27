"""Henter håndverkerbedrifter fra Brreg Enhetsregisteret API (gratis, ingen nøkkel).

Filtrerer på NACE-koder for byggfag og en kommune. Output: data/bedrifter.csv
"""
import time
import requests
import pandas as pd

BRREG_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"

# Brreg er av og til treg / timer ut på enkeltkall. En hel paginert henting tar
# ~5 min, og ett feilet kall skal ikke rive ned hele den daglige pipelinen.
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

# NACE-koder for håndverksfag som er aktuelle kjøpere av byggesaksleads
HANDVERKER_NACE = {
    "43.210": "Elektroinstallasjon",
    "43.220": "VVS og rørlegger",
    "43.291": "Isolasjonsarbeid",
    "43.320": "Snekkerarbeid/tømrer",
    "43.330": "Gulvlegging/flislegging",
    "43.341": "Malerarbeid",
    "43.910": "Takarbeid",
    "43.999": "Annen spesialisert bygge- og anleggsvirksomhet",
}


def fetch_bedrifter(kommunenummer: str, nace_koder: dict = None, sleep_s: float = 0.3) -> pd.DataFrame:
    """Hent alle aktive enheter for gitte NACE-koder i en kommune."""
    nace_koder = nace_koder or HANDVERKER_NACE
    rader = []

    for nace, bransje in nace_koder.items():
        page = 0
        while True:
            params = {
                "naeringskode": nace,
                "kommunenummer": kommunenummer,
                "size": 100,
                "page": page,
            }
            resp = _get_med_retry(BRREG_URL, params)
            resp.raise_for_status()
            data = resp.json()
            enheter = data.get("_embedded", {}).get("enheter", [])
            if not enheter:
                break

            for e in enheter:
                adresse = e.get("forretningsadresse", {}) or {}
                rader.append({
                    "organisasjonsnummer": e.get("organisasjonsnummer"),
                    "navn": e.get("navn"),
                    "nace_kode": nace,
                    "bransje": bransje,
                    "kommune": adresse.get("kommune"),
                    "kommunenummer": adresse.get("kommunenummer"),
                    "adresse": " ".join(adresse.get("adresse", []) or []),
                    "postnummer": adresse.get("postnummer"),
                    "poststed": adresse.get("poststed"),
                    "hjemmeside": e.get("hjemmeside"),
                    "epost": e.get("epostadresse"),
                    "telefon": e.get("telefon") or e.get("mobil"),
                    "antall_ansatte": e.get("antallAnsatte"),
                    "stiftelsesdato": e.get("stiftelsesdato"),
                })

            page_info = data.get("page", {})
            if page >= page_info.get("totalPages", 1) - 1:
                break
            page += 1
            time.sleep(sleep_s)

    # NB: dedupe på (org.nr, nace) - ikke bare org.nr - siden en bedrift kan drive
    # flere aktuelle håndverksfag og skal være kandidat for saker i alle sine bransjer.
    df = pd.DataFrame(rader).drop_duplicates(subset=["organisasjonsnummer", "nace_kode"])
    return df


if __name__ == "__main__":
    import sys
    kommunenummer = sys.argv[1] if len(sys.argv) > 1 else "5001"  # Trondheim
    df = fetch_bedrifter(kommunenummer)
    df.to_csv("data/bedrifter.csv", index=False)
    print(f"Lagret {len(df)} bedrifter til data/bedrifter.csv")
