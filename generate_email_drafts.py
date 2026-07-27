"""Genererer e-postutkast. Sender ALDRI selv - kun utkast til manuell godkjenning.

To bruksområder:
  1. generer_utkast(...)  -> data/email_drafts/  : ett .txt-utkast per topp-match,
     brukt av Streamlit-dashbordet (uendret, legacy).
  2. bygg_utboks(...)     -> data/utboks/        : én skreddersydd SALGS-e-post per
     håndverksbedrift, med et ekte, ferskt lead som gratis smakebit og lenke til
     landingssiden. Kun til upersonlige adresser (post@/firmapost@) jf.
     markedsføringsloven §15. Godkjennes og sendes med approve_and_send.py.

Input: data/matches.csv, data/kontaktet.csv (unngå dobbeltkontakt)
"""
import csv
import hashlib
import os
import re

import pandas as pd

from config import EMAIL_DRAFTS_DIR, PATHS, UTBOKS_DIR, env
from leads import anonymiser_adresse, er_upersonlig_epost, rensk_sakstype
from logg import get_logger

log = get_logger("utkast")

# --- Legacy: dashbord-utkast ----------------------------------------------
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

# --- Salgs-e-post til utboks ----------------------------------------------
SALG_MAL = """To: {epost}
Subject: Ny byggejobb i {omrade}: {sakstype}

Hei,

Det kom nettopp inn en ny byggesak som kan passe {bedrift_navn}:

  - Type:       {sakstype}
  - Område:     {omrade}
  - Registrert: {dato}

Dette er en gratis smakebit fra Byggesaksradar. Vi varsler deg ukentlig om nye
byggesaker innen ditt fag - rangert etter hvor godt de passer, med lenke til
saken hos kommunen. Full adresse og saksdetaljer får du som abonnent.

Prøv det for 99 kr/mnd, ingen binding:
{landingsside}

Ønsker du ikke slike tips? Svar "nei takk", så hører du ikke fra oss igjen.

Mvh
Byggesaksradar
{avsender}
"""


def trygg_filnavn(tekst: str) -> str:
    # Kort hash av HELE originalteksten sikrer unikhet selv om to lange
    # tekster (f.eks. URL-er som sak_id) deler samme 50-tegns prefiks.
    hash_suffix = hashlib.sha1(tekst.encode("utf-8")).hexdigest()[:8]
    lesbar_del = re.sub(r"[^a-zA-Z0-9_-]", "_", tekst)[:50]
    return f"{lesbar_del}_{hash_suffix}"


def generer_utkast(matches: pd.DataFrame, kontaktet: pd.DataFrame,
                   output_dir: str = EMAIL_DRAFTS_DIR, topp_n: int = 1):
    """Legacy: ett utkast per topp-match til dashbordvisning. Endres ikke."""
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


def bygg_utboks(matches: pd.DataFrame, kontaktet: pd.DataFrame,
                landingsside: str, output_dir: str = UTBOKS_DIR) -> int:
    """Lag én skreddersydd salgs-e-post per bedrift med bedriftens beste ferske lead.

    Regler som håndheves her:
      - Én e-post per bedrift (grupperer på org.nr, velger høyest score).
      - Kun upersonlige mottakeradresser (§15) - personlige adresser hoppes over.
      - Aldri bedrifter som allerede finnes i kontaktet.csv.
      - Adressen i smakebiten anonymiseres (gatenavn uten husnummer).

    Skriver også _manifest.csv slik at approve_and_send.py vet org.nr/sak_id per fil.
    Returnerer antall e-poster lagt i utboksen.
    """
    os.makedirs(output_dir, exist_ok=True)
    kontaktet_orgnr = set(kontaktet["organisasjonsnummer"].astype(str)) if not kontaktet.empty else set()
    avsender = env("AVSENDER_SIGNATUR", "")

    manifest_rader = []
    hoppet_personlig = hoppet_mangler = hoppet_kontaktet = 0

    # Én rad per bedrift: bedriftens høyest scorende (ferskeste) match
    beste_per_bedrift = (
        matches.sort_values(["score", "saksdato"], ascending=[False, False])
        .drop_duplicates(subset="organisasjonsnummer", keep="first")
    )

    for _, rad in beste_per_bedrift.iterrows():
        orgnr = str(rad["organisasjonsnummer"])
        epost = rad.get("epost")

        if orgnr in kontaktet_orgnr:
            hoppet_kontaktet += 1
            continue
        if not (isinstance(epost, str) and epost.strip()):
            hoppet_mangler += 1
            continue
        if not er_upersonlig_epost(epost):
            hoppet_personlig += 1
            continue

        innhold = SALG_MAL.format(
            epost=epost.strip(),
            bedrift_navn=rad["bedrift_navn"],
            sakstype=rensk_sakstype(rad.get("sakstype")),
            omrade=anonymiser_adresse(rad.get("sak_adresse")),
            dato=rad.get("saksdato") or "nylig",
            landingsside=landingsside,
            avsender=avsender,
        )
        filnavn = f"{trygg_filnavn(orgnr)}.txt"
        with open(os.path.join(output_dir, filnavn), "w", encoding="utf-8") as f:
            f.write(innhold)

        manifest_rader.append({
            "fil": filnavn,
            "organisasjonsnummer": orgnr,
            "sak_id": rad.get("sak_id"),
            "epost": epost.strip(),
            "bedrift_navn": rad.get("bedrift_navn"),
        })

    manifest_sti = os.path.join(output_dir, "_manifest.csv")
    with open(manifest_sti, "w", encoding="utf-8", newline="") as f:
        skriver = csv.DictWriter(
            f, fieldnames=["fil", "organisasjonsnummer", "sak_id", "epost", "bedrift_navn"])
        skriver.writeheader()
        skriver.writerows(manifest_rader)

    log.info(
        "Utboks: %d e-poster klare. Hoppet over: %d personlige adresser (§15), "
        "%d uten e-post, %d allerede kontaktet.",
        len(manifest_rader), hoppet_personlig, hoppet_mangler, hoppet_kontaktet,
    )
    return len(manifest_rader)


def _les_kontaktet() -> pd.DataFrame:
    try:
        return pd.read_csv(PATHS["kontaktet"], dtype={"organisasjonsnummer": str})
    except FileNotFoundError:
        return pd.DataFrame(columns=["organisasjonsnummer"])


if __name__ == "__main__":
    import sys

    matches = pd.read_csv(PATHS["matches"], dtype={"organisasjonsnummer": str, "sak_id": str})
    kontaktet = _les_kontaktet()

    if "--utboks" in sys.argv:
        landingsside = env("LANDINGSSIDE_URL", "https://din-landingsside.example/")
        antall = bygg_utboks(matches, kontaktet, landingsside)
        print(f"La {antall} salgs-e-poster i {UTBOKS_DIR}/ - godkjenn med: python approve_and_send.py")
    else:
        antall = generer_utkast(matches, kontaktet)
        print(f"Genererte {antall} e-postutkast i {EMAIL_DRAFTS_DIR}/")
        print("(Tips: 'python generate_email_drafts.py --utboks' lager salgs-e-poster til utboksen.)")
