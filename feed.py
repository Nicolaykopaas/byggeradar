"""Bygger "Finn-feed"-rader: nye byggesaker vist som annonser, anonymisert til postnr.

Delt av finn_feed.py (Streamlit) og build_feed_html.py (statisk side). Hver rad er
ÉN byggesak (ikke ett match-par). Vår egen visning er postnr-anonymisert. Lenken til
saken hos kommunen (`kilde_url`) er OFFENTLIG og eksponeres slik at hvert kort kan lenke
rett til kommunens egen saksside. Kun full gateadresse holdes tilbake (`_full_adresse`),
slik at en offentlig HTML-side aldri skriver den ut.
"""
from datetime import date

import pandas as pd

from config import PATHS
from kilder import kommune_info
from leads import rensk_sakstype


def _dager_siden(saksdato: str) -> int | None:
    try:
        d = pd.to_datetime(saksdato, errors="coerce")
        if pd.isna(d):
            return None
        return (pd.Timestamp(date.today()) - d.normalize()).days
    except Exception:  # noqa: BLE001
        return None


def bygg_feed_rader(maks: int = 200) -> list[dict]:
    """Returnerer feed-rader sortert nyest først. Tom liste hvis data mangler."""
    try:
        saker = pd.read_csv(
            PATHS["saker"],
            dtype={"sak_id": str, "postnummer": str, "kommunenummer": str},
        )
        matches = pd.read_csv(PATHS["matches"], dtype={"sak_id": str})
    except FileNotFoundError:
        return []
    if saker.empty or matches.empty:
        return []

    # Slå opp kommunenavn/fylke fra kilde-registeret (robust: CSV-en trenger ikke
    # inneholde disse kolonnene - vi filtrerer/viser ut fra kommunenummer).
    kominfo = kommune_info()  # {kommunenummer: (kommunenavn, fylke)}

    # Aggreger matcher per sak: hvilke fag er relevante, og beste score
    agg = (
        matches.groupby("sak_id")
        .agg(bransjer=("bransje", lambda x: sorted(set(x.dropna()))),
             score=("score", "max"))
        .reset_index()
    )
    df = saker.merge(agg, on="sak_id", how="inner")  # kun saker som faktisk matcher noe

    def _som_bool(v):
        """CSV-runde kan gi bool, np.bool eller "True"/"False"-tekst. None hvis mangler."""
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "ja")
        return bool(v)

    def _tekst(v) -> str:
        """Trygg tekst-verdi fra en CSV-celle (tom streng ved NaN/None)."""
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ""
        return str(v).strip()

    har_ps = "profesjonell_soker" in df.columns
    rader = []
    for _, r in df.iterrows():
        postnr = r.get("postnummer")
        postnr_str = str(postnr).strip() if isinstance(postnr, str) and postnr.strip() else ""

        # Geografi: kommunenummer fra saken, navn/fylke primært fra kilde-registeret,
        # med fallback til evt. kolonner i CSV-en, ellers tom streng.
        knr = _tekst(r.get("kommunenummer"))
        navn, fylke = kominfo.get(knr, ("", ""))
        if not navn and "kommunenavn" in df.columns:
            navn = _tekst(r.get("kommunenavn"))
        if not fylke and "fylke" in df.columns:
            fylke = _tekst(r.get("fylke"))

        omrade = postnr_str or (f"{navn} (postnr skjult)" if navn else "Postnr skjult")

        rader.append({
            # --- Offentlige, anonymiserte felt ---
            "sak_id": r["sak_id"],
            "sakstype": rensk_sakstype(r.get("sakstype")),
            "omrade": omrade,                         # KUN postnr, aldri gate
            "postnummer": postnr_str,
            "kommunenummer": knr,
            "kommunenavn": navn,
            "fylke": fylke,
            "bransjer": r.get("bransjer") or [],
            "score": int(round(float(r.get("score", 0)))),
            "saksdato": r.get("saksdato"),
            "status": r.get("status") if "status" in df.columns and isinstance(r.get("status"), str) else "",
            "profesjonell_soker": _som_bool(r.get("profesjonell_soker")) if har_ps else None,
            "dager_siden": _dager_siden(r.get("saksdato")),
            # --- Offentlig lenke til saken hos kommunen (kommunens egen side) ---
            "kilde_url": _tekst(r.get("kilde_url")),
            # --- Låst felt: full gateadresse skrives ALDRI ut i offentlig HTML ---
            "_full_adresse": r.get("adresse"),
        })

    rader.sort(key=lambda x: (x["saksdato"] or ""), reverse=True)
    return rader[:maks]


def ferskhet_etikett(dager_siden: int | None) -> str:
    if dager_siden is None:
        return ""
    if dager_siden <= 0:
        return "I dag"
    if dager_siden == 1:
        return "I går"
    if dager_siden <= 7:
        return f"{dager_siden} dager siden"
    return f"{dager_siden} dager siden"
