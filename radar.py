"""Kurateringslaget - gjør en flom av byggesaker om til «de få som er verdt tiden din».

Dette er kjernen i overhaulen. I stedet for å selge en kald adresse, hjelper vi
håndverkeren å SLIPPE å lese alt: vi klassifiserer hvert prosjekt etter skala,
regner en «mulighetsscore» (verdt-å-følge-opp), og gir et ÆRLIG, lovlig handlingstips.

Personvern: vi leser ALDRI tiltakshaver. All klassifisering skjer på offentlige,
upersonlige felt (arbeidsbeskrivelse/tittel, status, dato). Se CLAUDE.md.
"""
import re

from arbeid import arbeidssammendrag, tilgjengelighet
from feed import bygg_feed_rader

# Skala utledes KUN fra arbeidsbeskrivelsen (tittelen), aldri fra hvem som søker.
_STOR = [
    "nytt bygg", "nybygg", "rammetillatelse", "rammesøknad", "boligblokk",
    "leilighetsbygg", "næringsbygg", "næringsformål", "flermannsbolig",
    "tomannsbolig", "rekkehus", "boliger", "boligformål", "seksjoner",
    "riving og oppføring", "oppføring av", "leiligheter",
]
_LITEN = [
    "fasadeendring", "takvindu", "vindu", "pipe", "skorstein", "terrasse",
    "veranda", "balkong", "levegg", "gjerde", "forstøtning", "skilt",
    "solcelle", "mindre", "bod", "markise",
]
# alt annet (tilbygg, påbygg, garasje, enebolig, ombygging, bruksendring...) = middels


def prosjekt_skala(sakstype: str) -> str:
    t = (sakstype or "").lower()
    if any(o in t for o in _STOR):
        return "stor"
    if any(o in t for o in _LITEN):
        return "liten"
    return "middels"


_SKALA_BONUS = {"stor": 40, "middels": 20, "liten": 5}
_SKALA_ETIKETT = {"stor": "Stort prosjekt", "middels": "Middels", "liten": "Lite tiltak"}


def mulighetsscore(match_score: int, skala: str, dager_siden) -> int:
    """0-100: hvor verdt det er å følge opp. Vekter fagtreff, skala og ferskhet."""
    base = 0.5 * float(match_score)                 # fagtreff (0-50)
    base += _SKALA_BONUS.get(skala, 20)             # skala (5-40)
    if dager_siden is not None:                     # ferskhet (0-10)
        base += max(0, 10 - min(dager_siden, 10))
    return int(max(0, min(100, round(base))))


def handling_tips(omrade: str, proff: bool) -> str:
    """Handlingstips styrt av ETT signal: hvem som faktisk står som søker.

    Dette må samsvare med tilgjengelighet() - begge bruker profesjonell_soker,
    ikke prosjektstørrelse, så kortet aldri motsier seg selv.
    """
    if proff:
        return ("Ansvarlig søker er et foretak - hovedjobben er trolig tildelt. Realistisk "
                "vei inn: kontakt foretaket og tilby deg som underentreprenør/leverandør.")
    return (f"Ingen profesjonell søker registrert - størst sjanse for at de vil hyre inn. "
            f"Ikke masse-e-post til privatpersoner (§15); vær synlig i {omrade} eller ta "
            f"direkte kontakt på stedet.")


def bygg_radar(fag: list[str] = None, omrade_prefiks: str = "",
               min_mulighet: int = 0, maks_dager: int = 30,
               kommunenummer: str = None, fylke: str = None) -> list[dict]:
    """Kuraterte, filtrerte prosjekter sortert på mulighetsscore (høyest først).

    Geografi: `kommunenummer` og `fylke` filtrerer landsdekkende data ned til én
    kommune eller ett fylke (None = hele Norge). `omrade_prefiks` filtrerer videre
    på postnummer innen valget.
    """
    rader = []
    for r in bygg_feed_rader():
        if maks_dager and r["dager_siden"] is not None and r["dager_siden"] > maks_dager:
            continue
        if fag and not (set(fag) & set(r["bransjer"])):
            continue
        if kommunenummer and str(r.get("kommunenummer") or "") != str(kommunenummer):
            continue
        if fylke and str(r.get("fylke") or "") != str(fylke):
            continue
        if omrade_prefiks and not str(r["omrade"]).startswith(omrade_prefiks):
            continue

        skala = prosjekt_skala(r["sakstype"])
        # ETT autoritativt tilgjengelighetssignal: hvem som faktisk står som søker.
        # Prosjektstørrelse (skala) påvirker KUN mulighetsscoren, aldri ledig/tatt.
        proff = r.get("profesjonell_soker") is True
        mulighet = mulighetsscore(r["score"], skala, r["dager_siden"])
        if mulighet < min_mulighet:
            continue

        rader.append({
            **r,
            "skala": skala,
            "skala_etikett": _SKALA_ETIKETT[skala],
            "naeringsvennlig": proff,   # "kontaktbart foretak" == proff søker (samme signal)
            "mulighet": mulighet,
            "arbeid": arbeidssammendrag(r["sakstype"]),  # {overskrift, oppgaver[], fag[]}
            "tilgjengelighet": tilgjengelighet(r["sakstype"], r.get("profesjonell_soker")),
            "tips": handling_tips(r["omrade"], proff),
        })

    rader.sort(key=lambda x: x["mulighet"], reverse=True)
    return rader


def ukesammendrag(rader: list[dict]) -> dict:
    """Tall til «denne uka»-baren øverst i appen."""
    ferske = [r for r in rader if (r["dager_siden"] or 99) <= 7]
    return {
        "totalt": len(rader),
        "ferske_7d": len(ferske),
        "store": sum(1 for r in rader if r["skala"] == "stor"),
        "naeringsvennlige": sum(1 for r in rader if r["naeringsvennlig"]),
        "trolig_ledige": sum(1 for r in rader if r.get("profesjonell_soker") is False),
        "topp": rader[:3],
    }
