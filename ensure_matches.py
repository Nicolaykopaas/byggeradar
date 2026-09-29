"""Regner data/matches.csv fra saker+bedrifter hvis den mangler.

matches.csv er ca. 12 MB og endrer seg hver kjøring, så den committes ikke
til git (se .github/workflows/refresh-demo-data.yml, som kun committer de
små kildefilene). Offentlig-vendte sider (finn_feed.py) kaller denne ved
kald start i stedet.
"""
import os

import pandas as pd

import compute_scores
from config import PATHS


def ensure_matches() -> None:
    if os.path.exists(PATHS["matches"]):
        return
    saker = pd.read_csv(PATHS["saker"], dtype={
        "sak_id": str, "kommunenummer": str, "postnummer": str})
    bedrifter = pd.read_csv(PATHS["bedrifter"], dtype={
        "organisasjonsnummer": str, "nace_kode": str,
        "kommunenummer": str, "postnummer": str})
    matches = compute_scores.compute_scores(saker, bedrifter)
    matches.to_csv(PATHS["matches"], index=False)
