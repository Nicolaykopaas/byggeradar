"""Bygger "Finn-feed"-rader: nye byggesaker vist som annonser, anonymisert til postnr.

Delt av finn_feed.py (Streamlit) og build_feed_html.py (statisk side). Hver rad er
ÉN byggesak (ikke ett match-par). Offentlige felt er postnr-anonymisert; full adresse
og kilde-lenke er "låst" (bak et tenkt kjøp/abonnement) og ligger i egne nøkler slik at
en offentlig HTML-side aldri trenger å skrive dem ut.
"""
from datetime import date

import pandas as pd

from config import PATHS
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
        saker = pd.read_csv(PATHS["saker"], dtype={"sak_id": str, "postnummer": str})
        matches = pd.read_csv(PATHS["matches"], dtype={"sak_id": str})
    except FileNotFoundError:
        return []
    if saker.empty or matches.empty:
        return []

    # Aggreger matcher per sak: hvilke fag er relevante, og beste score
    agg = (
        matches.groupby("sak_id")
        .agg(bransjer=("bransje", lambda x: sorted(set(x.dropna()))),
             score=("score", "max"))
        .reset_index()
    )
    df = saker.merge(agg, on="sak_id", how="inner")  # kun saker som faktisk matcher noe

    rader = []
    for _, r in df.iterrows():
        postnr = r.get("postnummer")
        omrade = str(postnr) if isinstance(postnr, str) and postnr.strip() else "Bergen (postnr skjult)"
        rader.append({
            # --- Offentlige, anonymiserte felt ---
            "sak_id": r["sak_id"],
            "sakstype": rensk_sakstype(r.get("sakstype")),
            "omrade": omrade,                         # KUN postnr, aldri gate
            "bransjer": r.get("bransjer") or [],
            "score": int(round(float(r.get("score", 0)))),
            "saksdato": r.get("saksdato"),
            "status": r.get("status") if "status" in df.columns and isinstance(r.get("status"), str) else "",
            "dager_siden": _dager_siden(r.get("saksdato")),
            # --- Låste felt (vises aldri i offentlig HTML) ---
            "_full_adresse": r.get("adresse"),
            "_kilde_url": r.get("kilde_url"),
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
