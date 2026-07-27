"""Kontrakt for kilde-adaptere: én adapter per kommune, standardisert output.

Slik skalerer vi mot landsdekkende uten å skrive om resten: legg til en ny fil
kilder/<kommune>.py som definerer en Kilde-underklasse og en modulvariabel
KILDE = MinKommuneKilde(). Da plukkes den automatisk opp av kilder.alle_kilder().

Hver fetch_saker() returnerer en liste med dict-er med NØYAKTIG disse nøklene
(SAK_KOLONNER). Bare ekte byggesaker (ikke henvendelser/klager) skal med.

PERSONVERN: 'profesjonell_soker' er en boolean utledet fra ansvarlig søker -
navnet på søker/tiltakshaver skal ALDRI lagres eller returneres. Se
er_profesjonell_soker().
"""
import re
import time

import requests

REQUEST_TIMEOUT = 30

SAK_KOLONNER = [
    "sak_id", "kommunenummer", "kommunenavn", "fylke", "postnummer",
    "adresse", "saksdato", "sakstype", "status", "profesjonell_soker", "kilde_url",
]

# Foretaks-kjennetegn: selskapsformer (hele ord) + typiske bransjeord i firmanavn.
_FORETAK = re.compile(
    r"\b(AS|ASA|ANS|DA|BA|SA|NUF|KS|ENK)\b|BYGG|ENTREPREN|EIENDOM|PROSJEKT|"
    r"UTVIKLING|HOLDING|GRUPPEN|INVEST|ANLEGG|MASKIN|ARKITEKT|BOLIG|TOMTE", re.I)


def get_med_retry(url: str, params: dict = None, timeout: int = REQUEST_TIMEOUT,
                  forsok: int = 3) -> requests.Response:
    """GET med eksponentiell backoff (1s, 2s, 4s) ved nettverksfeil/timeout.

    Hever siste feil hvis alle forsøk feiler. Ingen ekstern retry-pakke.
    """
    siste = None
    for n in range(forsok):
        try:
            return requests.get(url, params=params, timeout=timeout)
        except requests.exceptions.RequestException as exc:
            siste = exc
            if n < forsok - 1:
                time.sleep(2 ** n)
    raise siste


def er_profesjonell_soker(soker) -> bool:
    """Leser KUN for å utlede ja/nei - navnet lagres aldri (personvern).

    True hvis ansvarlig søker ser ut som et foretak (AS o.l.), ellers False.
    """
    if not soker:
        return False
    tekst = " ".join(soker) if isinstance(soker, list) else str(soker)
    return bool(_FORETAK.search(tekst))


def postnummer_fra(adresse_liste) -> str | None:
    """Trekk ut firesifret postnummer fra en adresse som 'Gata 1, 5230 Paradis'."""
    if not adresse_liste:
        return None
    tekst = adresse_liste[0] if isinstance(adresse_liste, list) else str(adresse_liste)
    m = re.search(r"\b(\d{4})\b", tekst)
    return m.group(1) if m else None


def gateadresse_fra(adresse_liste) -> str | None:
    if not adresse_liste:
        return None
    tekst = adresse_liste[0] if isinstance(adresse_liste, list) else str(adresse_liste)
    return tekst.split(",")[0].strip()


class Kilde:
    """Basisklasse for en kommunes byggesak-adapter.

    Underklasser setter kommunenummer/kommunenavn/fylke og implementerer
    fetch_saker(). VIKTIG: verifiser robots.txt for kommunens innsyn-portal FØR
    du skraper, og skrap kun endepunkt som ikke er blokkert.
    """
    kommunenummer: str = ""
    kommunenavn: str = ""
    fylke: str = ""

    def fetch_saker(self, rows: int = 150) -> list[dict]:
        """Returner liste av dict-er med nøklene i SAK_KOLONNER. Kun ekte byggesaker."""
        raise NotImplementedError

    def _rad(self, **kwargs) -> dict:
        """Hjelper: fyll ut en standardrad med kommune-metadata + gitte felt."""
        rad = {k: None for k in SAK_KOLONNER}
        rad["kommunenummer"] = self.kommunenummer
        rad["kommunenavn"] = self.kommunenavn
        rad["fylke"] = self.fylke
        rad.update(kwargs)
        return rad
