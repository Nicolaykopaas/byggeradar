"""Bakoverkompatibel wrapper rundt Bergen-kilden (kilder/bergen.py).

Bergen-logikken bor nå i kilde-adapteren `kilder.bergen.BergenKilde` slik at
pipelinen kan skalere til flere kommuner (se kilder/base.py). Denne modulen
beholdes som en tynn fasade så eksisterende importer (helsesjekk.py, m.fl.)
fortsatt virker: `fetch_saker(rows, sleep_s)` returnerer som før en pandas
DataFrame, og __main__ skriver fortsatt data/saker.csv.

VIKTIG (personvern): tiltakshaver leses aldri. Feltet "soker" leses kun for å
utlede boolean-flagget `profesjonell_soker`. Se kilder/bergen.py.
"""
import pandas as pd

from kilder import base
from kilder.bergen import BergenKilde, BERGEN_API_URL, BERGEN_SAK_URL_MAL

# Bakoverkompatible modulnavn (noe kan importere disse).
BERGEN_KOMMUNENUMMER = BergenKilde.kommunenummer

# Delte hjelpere ligger nå i kilder.base - re-eksporteres under sine gamle navn
# for moduler/tester som fortsatt importerer dem herfra.
_get_med_retry = base.get_med_retry
_er_profesjonell_soker = base.er_profesjonell_soker


def fetch_saker(rows: int = 100, sleep_s: float = 0.3) -> pd.DataFrame:
    """Hent de `rows` sist innkomne byggesakene fra Bergen som DataFrame.

    Delegerer til BergenKilde().fetch_saker og pakker listen i en DataFrame
    (samme returtype som før flytten til kilde-adaptere).
    """
    rader = BergenKilde().fetch_saker(rows=rows, sleep_s=sleep_s)
    return pd.DataFrame(rader, columns=base.SAK_KOLONNER)


if __name__ == "__main__":
    import sys
    rows = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    df = fetch_saker(rows=rows)
    df.to_csv("data/saker.csv", index=False)
    print(f"Lagret {len(df)} byggesaker til data/saker.csv")
