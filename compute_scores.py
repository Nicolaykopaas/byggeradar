"""Regner ut matchscore (0-100) mellom byggesaker og håndverkerbedrifter.

Input: data/saker.csv (fra byggesak_fetch.py), data/bedrifter.csv (fra brreg_fetch.py)
Output: data/matches.csv, sortert synkende på score
"""
import pandas as pd

# Sakstype (fritekst fra kommunen) -> aktuell NACE-bransje.
# Nøkler matches med "in"-sjekk mot sakstype (lowercase), ikke eksakt likhet.
SAKSTYPE_TIL_NACE = {
    "elektro": "43.210",
    "rør": "43.220",
    "vvs": "43.220",
    "sanitær": "43.220",
    "isolasjon": "43.291",
    "tømrer": "43.320",
    "snekker": "43.320",
    "tilbygg": "43.320",
    "påbygg": "43.320",
    "gulv": "43.330",
    "flis": "43.330",
    "mal": "43.341",
    "tak": "43.910",
    "rehabilitering": "43.999",
}

VEKT_BRANSJE = 60
VEKT_GEOGRAFI = 30
VEKT_STORRELSE = 10


def gjett_nace_fra_sakstype(sakstype: str) -> str | None:
    sakstype_lower = (sakstype or "").lower()
    for nokkelord, nace in SAKSTYPE_TIL_NACE.items():
        if nokkelord in sakstype_lower:
            return nace
    return None


def compute_scores(saker: pd.DataFrame, bedrifter: pd.DataFrame) -> pd.DataFrame:
    saker = saker.copy()
    saker["gjettet_nace"] = saker["sakstype"].apply(gjett_nace_fra_sakstype)

    rader = []
    for _, sak in saker.iterrows():
        if sak["gjettet_nace"] is None:
            continue

        kandidater = bedrifter[bedrifter["nace_kode"] == sak["gjettet_nace"]]
        for _, bedrift in kandidater.iterrows():
            score = 0

            # Bransjematch: alt-eller-intet siden vi allerede har filtrert på nace_kode
            score += VEKT_BRANSJE

            # Geografi: samme kommune gir full uttelling
            if str(sak.get("kommunenummer")) == str(bedrift.get("kommunenummer")):
                score += VEKT_GEOGRAFI
            elif str(sak.get("postnummer", ""))[:2] == str(bedrift.get("postnummer", ""))[:2]:
                score += VEKT_GEOGRAFI * 0.5

            # Størrelse: 1-20 ansatte er typisk beste kunde (nok kapasitet, høy betalingsvilje)
            ansatte = bedrift.get("antall_ansatte")
            if pd.notna(ansatte) and 1 <= ansatte <= 20:
                score += VEKT_STORRELSE
            elif pd.notna(ansatte) and ansatte > 20:
                score += VEKT_STORRELSE * 0.5

            rader.append({
                "sak_id": sak.get("sak_id"),
                "sak_adresse": sak.get("adresse"),
                "sakstype": sak.get("sakstype"),
                "saksdato": sak.get("saksdato"),
                "organisasjonsnummer": bedrift.get("organisasjonsnummer"),
                "bedrift_navn": bedrift.get("navn"),
                "bransje": bedrift.get("bransje"),
                "score": round(score, 1),
            })

    matches = pd.DataFrame(rader).sort_values("score", ascending=False)
    return matches


if __name__ == "__main__":
    # dtype=str er nødvendig: uten det tolker pandas koder som "43.210" og
    # postnumre med ledende null (f.eks. "0170") som tall og ødelegger matching.
    saker = pd.read_csv("data/saker.csv", dtype={"kommunenummer": str, "postnummer": str, "sak_id": str})
    bedrifter = pd.read_csv("data/bedrifter.csv", dtype={
        "organisasjonsnummer": str, "nace_kode": str, "kommunenummer": str, "postnummer": str,
    })
    matches = compute_scores(saker, bedrifter)
    matches.to_csv("data/matches.csv", index=False)
    print(f"Lagret {len(matches)} matcher til data/matches.csv")
