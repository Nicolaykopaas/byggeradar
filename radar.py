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


def er_naeringsvennlig(sakstype: str, skala: str) -> bool:
    """Store prosjekter har som regel et ANSVARLIG FORETAK (offentlig i saksdok) -
    en bedrift du kan kontakte lovlig, i motsetning til en privat tiltakshaver."""
    return skala == "stor"


def handling_tips(omrade: str, skala: str, naering: bool) -> str:
    if naering:
        return ("Større prosjekt: åpne saken hos kommunen og se etter ansvarlig "
                "søkerforetak - det er en bedrift du kan kontakte direkte og lovlig.")
    return (f"Trolig privat tiltakshaver - ikke masse-e-post (§15). Vær synlig i "
            f"{omrade}: skilt/flyer i området, eller ta direkte kontakt på stedet.")


def bygg_radar(fag: list[str] = None, omrade_prefiks: str = "",
               min_mulighet: int = 0, maks_dager: int = 30) -> list[dict]:
    """Kuraterte, filtrerte prosjekter sortert på mulighetsscore (høyest først)."""
    rader = []
    for r in bygg_feed_rader():
        if maks_dager and r["dager_siden"] is not None and r["dager_siden"] > maks_dager:
            continue
        if fag and not (set(fag) & set(r["bransjer"])):
            continue
        if omrade_prefiks and not str(r["omrade"]).startswith(omrade_prefiks):
            continue

        skala = prosjekt_skala(r["sakstype"])
        naering = er_naeringsvennlig(r["sakstype"], skala)
        mulighet = mulighetsscore(r["score"], skala, r["dager_siden"])
        if mulighet < min_mulighet:
            continue

        rader.append({
            **r,
            "skala": skala,
            "skala_etikett": _SKALA_ETIKETT[skala],
            "naeringsvennlig": naering,
            "mulighet": mulighet,
            "arbeid": arbeidssammendrag(r["sakstype"]),  # {overskrift, oppgaver[], fag[]}
            "tilgjengelighet": tilgjengelighet(r["sakstype"], naering, r.get("profesjonell_soker")),
            "tips": handling_tips(r["omrade"], skala, naering),
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
