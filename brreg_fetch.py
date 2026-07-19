"""Henter håndverkerbedrifter fra Brreg Enhetsregisteret API (gratis, ingen nøkkel).

Filtrerer på NACE-koder for byggfag og en kommune. Output: data/bedrifter.csv
"""
import time
import requests
import pandas as pd

BRREG_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"

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
            resp = requests.get(BRREG_URL, params=params, timeout=20)
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
                    "antall_ansatte": e.get("antallAnsatte"),
                    "stiftelsesdato": e.get("stiftelsesdato"),
                })

            page_info = data.get("page", {})
            if page >= page_info.get("totalPages", 1) - 1:
                break
            page += 1
            time.sleep(sleep_s)

    df = pd.DataFrame(rader).drop_duplicates(subset="organisasjonsnummer")
    return df


if __name__ == "__main__":
    import sys
    kommunenummer = sys.argv[1] if len(sys.argv) > 1 else "5001"  # Trondheim
    df = fetch_bedrifter(kommunenummer)
    df.to_csv("data/bedrifter.csv", index=False)
    print(f"Lagret {len(df)} bedrifter til data/bedrifter.csv")
