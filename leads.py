"""Delte hjelpefunksjoner for leads: §15-e-postfilter, anonymisering og eksempelvalg.

Brukes av både build_landing.py (eksempel-lead på landingssiden) og
generate_email_drafts.py (utvalg + adressat-sjekk).
"""
import re

import pandas as pd

# Markedsføringsloven §15: e-postmarkedsføring til fysiske personer krever
# samtykke. Til virksomheter på generelle, upersonlige adresser (ikke knyttet til
# en navngitt person) er det tillatt. Vi sender KUN til slike rolleadresser.
UPERSONLIGE_PREFIKSER = {
    "post", "firmapost", "kontakt", "hei", "hallo", "mail", "e-post", "epost",
    "info", "kundeservice", "kundesenter", "salg", "ordre", "bestilling",
    "faktura", "regnskap", "adm", "admin", "administrasjon", "drift", "service",
    "verksted", "resepsjon", "styret", "ledelse", "office", "kontor",
}


def er_upersonlig_epost(epost) -> bool:
    """True hvis e-posten er en generell virksomhetsadresse (post@, firmapost@, ...).

    Avviser personlige adresser (fornavn.etternavn@, ola@) for å være på trygg
    side ift. §15. Tomme/ugyldige adresser gir False.
    """
    if not isinstance(epost, str):
        return False
    epost = epost.strip().lower()
    if "@" not in epost or epost.count("@") != 1:
        return False
    lokal = epost.split("@", 1)[0]
    # Del opp på skilletegn: "post.bergen" -> {"post", "bergen"}
    biter = set(re.split(r"[.\-_+]", lokal))
    return bool(biter & UPERSONLIGE_PREFIKSER) or lokal in UPERSONLIGE_PREFIKSER


def anonymiser_adresse(adresse) -> str:
    """Fjerner husnummer slik at en eksakt privatadresse ikke publiseres.

    "Paradisleitet 12B" -> "Paradisleitet". Beholder gatenavn for realisme.
    Se personvern-regelen i CLAUDE.md: aldri eksponer privatpersoners adresse.
    """
    if not isinstance(adresse, str) or not adresse.strip():
        return "et område i kommunen"
    uten_husnr = re.sub(r"\s+\d+\s*[A-Za-z]?$", "", adresse.strip())
    return uten_husnr or adresse.strip()


def rensk_sakstype(tittel) -> str:
    """Rens kommunens sakstittel ned til selve arbeidsbeskrivelsen.

    Bergen-titler har formen "<matrikkel> <adresse>, <beskrivelse>", f.eks.
    "82/233/0/0 Vallaheiane 141, tilbygg og fasadeendring mm". Både matrikkelkode
    og den eksakte adressen (med husnummer!) må fjernes - ellers lekker
    privatadressen ut i emnefelt/smakebit tross anonymiseringen ellers.
    """
    if not isinstance(tittel, str) or not tittel.strip():
        return "Byggesak"
    t = tittel.strip()
    t = re.sub(r"^[\d/\s]+", "", t)          # fjern ledende matrikkelkode
    if "," in t:                              # adressen står før første komma
        t = t.split(",", 1)[1]
    t = t.strip(" .;-")
    if not t:
        return "Byggesak"
    return t[0].upper() + t[1:]


def velg_eksempel_lead(matches: pd.DataFrame) -> dict | None:
    """Plukk én representativ, anonymisert match til bruk som gratis smakebit."""
    if matches is None or matches.empty:
        return None
    beste = matches.sort_values("score", ascending=False).iloc[0]
    return {
        "sakstype": rensk_sakstype(beste.get("sakstype")),
        "omrade": anonymiser_adresse(beste.get("sak_adresse")),
        "bransje": beste.get("bransje") or "håndverk",
        "score": int(round(float(beste.get("score", 0)))),
        "dato": beste.get("saksdato") or "",
    }
