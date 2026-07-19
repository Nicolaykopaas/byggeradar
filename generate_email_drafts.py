"""Genererer e-postutkast for topp-matcher. Sender ALDRI selv - kun utkast til manuell gjennomgang.

Input: data/matches.csv, data/kontaktet.csv (for å unngå dobbel kontakt)
Output: én .txt-fil per match i data/email_drafts/
"""
import os
import re
import pandas as pd

EMAIL_MAL = """Til: {epost}
Emne: Ny jobbmulighet i {sak_adresse}

Hei {bedrift_navn},

Vi så at det nylig kom inn en byggesak av type "{sakstype}" på {sak_adresse} ({saksdato}).
Dette kan være en aktuell jobb for dere før konkurrentene rekker å ta kontakt.

Vil dere ha løpende varsling om nye byggesaker i deres område og bransje?
Første varsel er gratis - svar på denne e-posten for å høre mer.

Mvh
Byggesaksradar
"""


def trygg_filnavn(tekst: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", tekst)[:80]


def generer_utkast(matches: pd.DataFrame, kontaktet: pd.DataFrame, output_dir: str = "data/email_drafts", topp_n: int = 1):
    os.makedirs(output_dir, exist_ok=True)
    kontaktet_orgnr = set(kontaktet["organisasjonsnummer"].astype(str)) if not kontaktet.empty else set()

    antall = 0
    for sak_id, gruppe in matches.groupby("sak_id"):
        beste = gruppe.sort_values("score", ascending=False).head(topp_n)
        for _, rad in beste.iterrows():
            if str(rad["organisasjonsnummer"]) in kontaktet_orgnr:
                continue

            innhold = EMAIL_MAL.format(
                epost=rad.get("epost") or "(mangler e-post - sjekk manuelt)",
                bedrift_navn=rad["bedrift_navn"],
                sak_adresse=rad["sak_adresse"],
                sakstype=rad["sakstype"],
                saksdato=rad["saksdato"],
            )
            filnavn = f"{trygg_filnavn(str(sak_id))}_{trygg_filnavn(str(rad['organisasjonsnummer']))}.txt"
            with open(os.path.join(output_dir, filnavn), "w", encoding="utf-8") as f:
                f.write(innhold)
            antall += 1

    return antall


if __name__ == "__main__":
    matches = pd.read_csv("data/matches.csv", dtype={"organisasjonsnummer": str, "sak_id": str})
    try:
        kontaktet = pd.read_csv("data/kontaktet.csv", dtype={"organisasjonsnummer": str})
    except FileNotFoundError:
        kontaktet = pd.DataFrame(columns=["organisasjonsnummer"])

    antall = generer_utkast(matches, kontaktet)
    print(f"Genererte {antall} e-postutkast i data/email_drafts/")
