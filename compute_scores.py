"""Regner ut matchscore (0-100) mellom byggesaker og håndverkerbedrifter.

Input: data/saker.csv (fra byggesak_fetch.py), data/bedrifter.csv (fra brreg_fetch.py)
Output: data/matches.csv, sortert synkende på score

Modell:
- En sakstittel er fritekst fra kommunen ("... tilbygg og fasadeendring mm").
  Ett tiltak berører ofte FLERE fag, så vi mapper sakstype -> et SETT av NACE-
  bransjer (ikke bare én). Se SAKSTYPE_TIL_NACE_SETT.
- Scoren vektes over fire ledd og er laget for å skille leads fra hverandre
  (ikke flat 90+): bransje-spesifisitet, geografisk nærhet, ferskhet, størrelse.
"""
import re
from datetime import date

import pandas as pd

# Sakstype (fritekst fra kommunen) -> SETT av aktuelle NACE-bransjer.
# Nøkler matches med ordgrense-regex mot sakstype (lowercase), ikke eksakt likhet.
#
# Presise ord peker på ÉN bransje ("takomlegging" -> tak). Brede ord peker på
# flere fordi arbeidet faktisk spenner over mange fag ("tilbygg" -> tømrer OG
# tak OG maler OG rør). Antallet bransjer en sak treffer brukes senere som mål
# på hvor spesifikk (og dermed verdifull) leaden er: færre bransjer = mer presist.
#
# NACE-koder (jf. brreg_fetch.HANDVERKER_NACE):
#   43.210 Elektro   43.220 VVS/rør   43.291 Isolasjon   43.320 Snekker/tømrer
#   43.330 Gulv/flis 43.341 Maler     43.910 Tak         43.999 Annen spesialisert
SAKSTYPE_TIL_NACE_SETT = {
    # --- Presise, enkeltfag ---
    "elektro": ("43.210",),
    "elektrisk": ("43.210",),
    "el-anlegg": ("43.210",),
    "solcelle": ("43.210",),
    "lading": ("43.210",),
    "ladepunkt": ("43.210",),
    "rør": ("43.220",),
    "vvs": ("43.220",),
    "sanitær": ("43.220",),
    "ventilasjon": ("43.220",),
    "va-anlegg": ("43.220",),
    "va anlegg": ("43.220",),
    "avløp": ("43.220",),
    "isolasjon": ("43.291",),
    "isoler": ("43.291",),
    "etterisoler": ("43.291",),
    "gulv": ("43.330",),
    "parkett": ("43.330",),
    "flis": ("43.330",),
    "mal": ("43.341",),      # \b hindrer treff i "normal"; se gjett_-funksjonen
    "overflatebehandling": ("43.341",),
    "tak": ("43.910",),      # \b hindrer treff i "kontakt"
    "yttertak": ("43.910",),
    "taktekking": ("43.910",),
    "takomlegging": ("43.910",),
    "takvindu": ("43.910",),
    # --- Riving / grunn / anlegg / annen spesialisert ---
    "riving": ("43.999",),
    "rive": ("43.999",),
    "mur": ("43.999",),      # \b hindrer treff i "murer"-uklarhet; dekker "mur mot vei"
    "grunnmur": ("43.999",),
    "betong": ("43.999",),
    "skilt": ("43.999",),
    "reklame": ("43.999",),
    "vei": ("43.999",),
    "veg": ("43.999",),      # "veg", "veganlegg"
    "parkeringsplass": ("43.999",),
    "terrenginngrep": ("43.999",),
    "avfallsløsning": ("43.999",),
    "pipe": ("43.999",),
    "skorstein": ("43.999",),
    "ildsted": ("43.999",),
    # --- Brede tiltak (flere fag) ---
    "tilbygg": ("43.320", "43.910", "43.341", "43.220"),
    "påbygg": ("43.320", "43.910", "43.341"),
    "utvidelse": ("43.320", "43.910"),
    "garasje": ("43.320", "43.910"),
    "carport": ("43.320", "43.910"),
    "uthus": ("43.320", "43.910"),
    "terrasse": ("43.320",),
    "veranda": ("43.320",),
    "balkong": ("43.320",),
    "altan": ("43.320",),
    "vindu": ("43.320",),
    "kledning": ("43.341", "43.320"),
    "panel": ("43.341", "43.320"),
    "fasade": ("43.341", "43.320", "43.291"),
    "vegg": ("43.320",),
    "bærekonstruksjon": ("43.320",),
    "bærende": ("43.320",),
    "konstruksjon": ("43.320",),
    "snekker": ("43.320",),
    "tømrer": ("43.320",),
    "loft": ("43.320", "43.291"),
    "kjeller": ("43.320", "43.291"),
    "kjelder": ("43.320", "43.291"),
    "bad": ("43.220", "43.330"),
    "våtrom": ("43.220", "43.330"),
    "kjøkken": ("43.320", "43.220", "43.210", "43.330"),
    # Nybygg/bolig: hele huset -> mange fag (bevisst bredt = lav spesifisitet)
    "nybygg": ("43.320", "43.210", "43.910", "43.330", "43.341"),
    "nytt bygg": ("43.320", "43.210", "43.910", "43.330", "43.341"),
    "nye bolig": ("43.320", "43.210", "43.910", "43.330", "43.341"),
    "oppføring": ("43.320", "43.210", "43.910", "43.330"),
    "enebolig": ("43.320", "43.210", "43.910", "43.330", "43.341"),
    "boligformål": ("43.320", "43.210", "43.910", "43.330"),
    "fritidsbolig": ("43.320", "43.210", "43.910"),
    "leilighet": ("43.320", "43.210", "43.330"),
    # Ombygging / bruksendring: innvendig rehab -> flere fag
    "ombygging": ("43.320", "43.210", "43.330", "43.341"),
    "ombygg": ("43.320", "43.210", "43.330", "43.341"),
    "innvendig": ("43.320", "43.210", "43.330", "43.341"),
    "innvending": ("43.320", "43.210", "43.330", "43.341"),  # vanlig skrivefeil i titlene
    "rehabilitering": ("43.320", "43.210", "43.330", "43.341"),
    "renovering": ("43.320", "43.210", "43.330", "43.341"),
    "oppgradering": ("43.320", "43.210", "43.341"),
    "bruksendring": ("43.320", "43.210", "43.910", "43.330"),
    "byggetiltak": ("43.320", "43.999"),
    "byggesøknad": ("43.320", "43.999"),
}

# Bakoverkompatibel enkeltkode-tabell (andre moduler kan importere denne).
# Avledes fra sett-tabellen ved å ta den mest sannsynlige (første) bransjen.
SAKSTYPE_TIL_NACE = {ord: koder[0] for ord, koder in SAKSTYPE_TIL_NACE_SETT.items()}

# Vekter summerer til 100. Bransje veier mest, men geografi/ferskhet/størrelse
# er tunge nok til at scoren faktisk spres og topp-lista rangerer.
VEKT_BRANSJE = 50
VEKT_GEOGRAFI = 25
VEKT_FERSKHET = 15
VEKT_STORRELSE = 10

# Ferskhet trappes lineært ned til 0 over så mange dager.
FERSKHET_DAGER = 30


def gjett_nace_sett_fra_sakstype(sakstype: str) -> set:
    """Returnerer settet av ALLE aktuelle NACE-bransjer for en sakstype.

    En sak kan være relevant for flere fag samtidig (f.eks. "tilbygg og
    fasadeendring" -> tømrer, tak, maler, isolasjon). Tomt sett = ingen match.
    """
    sakstype_lower = (sakstype or "").lower()
    treff = set()
    for nokkelord, nace_koder in SAKSTYPE_TIL_NACE_SETT.items():
        # \b foran nøkkelordet unngår falske treff som "mal" i "normal" eller "tak" i "kontakt"
        if re.search(rf"\b{re.escape(nokkelord)}", sakstype_lower):
            treff.update(nace_koder)
    return treff


def gjett_nace_fra_sakstype(sakstype: str):
    """Bakoverkompatibel: returnerer ÉN NACE-kode (første treff) eller None.

    Beholdt for moduler som forventer den gamle signaturen. Ny kode bør bruke
    gjett_nace_sett_fra_sakstype som gir hele settet av aktuelle bransjer.
    """
    sakstype_lower = (sakstype or "").lower()
    for nokkelord, nace_koder in SAKSTYPE_TIL_NACE_SETT.items():
        # \b foran nøkkelordet unngår falske treff som "mal" i "normal" eller "tak" i "kontakt"
        if re.search(rf"\b{re.escape(nokkelord)}", sakstype_lower):
            return nace_koder[0]
    return None


def bransjescore(antall_bransjer_i_sak: int) -> float:
    """Uttelling for at bedriftens bransje treffer saken.

    Jo færre bransjer saken peker på, jo mer presist er treffet og jo høyere
    score. En "takomlegging" (1 bransje) er en langt varmere lead for en
    takentreprenør enn en generisk "bruksendring" (4 bransjer) er for hvem
    som helst av fagene.
    """
    if antall_bransjer_i_sak <= 0:
        return 0.0
    spesifisitet = max(0.35, 1.0 - 0.14 * (antall_bransjer_i_sak - 1))
    return VEKT_BRANSJE * spesifisitet


def geografiscore(sak_postnr, bedrift_postnr, sak_kommune, bedrift_kommune) -> float:
    """Gradert geografisk nærhet. Innen samme kommune varierer den fortsatt
    på postnummer, slik at nære bedrifter rangeres foran fjerne."""
    sp = str(sak_postnr or "").strip()
    bp = str(bedrift_postnr or "").strip()
    if len(sp) == 4 and sp.isdigit() and len(bp) == 4 and bp.isdigit():
        if sp[:3] == bp[:3]:
            return VEKT_GEOGRAFI            # samme postnr-område (3 siffer)
        if sp[:2] == bp[:2]:
            return VEKT_GEOGRAFI * 0.6      # samme bydelsregion (2 siffer)
    # Fallback / manglende postnr: samme kommune gir svak uttelling
    if str(sak_kommune) == str(bedrift_kommune):
        return VEKT_GEOGRAFI * 0.3
    return 0.0


def _parse_dato(verdi):
    try:
        return date.fromisoformat(str(verdi)[:10])
    except (ValueError, TypeError):
        return None


def ferskhetscore(saksdato, referansedato) -> float:
    """Nyere sak = høyere score. Lineær nedtrapping til 0 over FERSKHET_DAGER."""
    d = _parse_dato(saksdato)
    if d is None or referansedato is None:
        return 0.0
    dager = (referansedato - d).days
    if dager <= 0:
        return VEKT_FERSKHET
    if dager >= FERSKHET_DAGER:
        return 0.0
    return VEKT_FERSKHET * (1 - dager / FERSKHET_DAGER)


def storrelsescore(antall_ansatte) -> float:
    """1-20 ansatte er typisk beste kunde (nok kapasitet, høy betalingsvilje)."""
    if pd.notna(antall_ansatte) and 1 <= antall_ansatte <= 20:
        return VEKT_STORRELSE
    if pd.notna(antall_ansatte) and antall_ansatte > 20:
        return VEKT_STORRELSE * 0.5
    return 0.0


def compute_scores(saker: pd.DataFrame, bedrifter: pd.DataFrame) -> pd.DataFrame:
    saker = saker.copy()
    saker["gjettet_nace_sett"] = saker["sakstype"].apply(gjett_nace_sett_fra_sakstype)

    # Referansedato for ferskhet = nyeste sak i datasettet. Robust mot at
    # datagrunnlaget er noen dager gammelt (uavhengig av klokka på maskinen).
    datoer = [d for d in (_parse_dato(x) for x in saker["saksdato"]) if d is not None]
    referansedato = max(datoer) if datoer else None

    # Indekser bedrifter på NACE for rask oppslag per bransje.
    bedrifter_per_nace = {nace: gruppe for nace, gruppe in bedrifter.groupby("nace_kode")}

    rader = []
    for _, sak in saker.iterrows():
        nace_sett = sak["gjettet_nace_sett"]
        if not nace_sett:
            continue

        antall_bransjer = len(nace_sett)
        b_score = bransjescore(antall_bransjer)
        f_score = ferskhetscore(sak.get("saksdato"), referansedato)
        sak_kommune = str(sak.get("kommunenummer"))

        for nace in nace_sett:
            kandidater = bedrifter_per_nace.get(nace)
            if kandidater is None:
                continue
            # KRITISK (flerkommune): en sak skal KUN matches mot bedrifter i
            # SAMME kommune. Uten dette ville f.eks. Bergen-saker matchet andre
            # kommuners bedrifter og gitt en eksplosjon i (irrelevante) rader.
            kandidater = kandidater[kandidater["kommunenummer"].astype(str) == sak_kommune]
            for _, bedrift in kandidater.iterrows():
                g_score = geografiscore(
                    sak.get("postnummer"), bedrift.get("postnummer"),
                    sak.get("kommunenummer"), bedrift.get("kommunenummer"),
                )
                s_score = storrelsescore(bedrift.get("antall_ansatte"))
                score = b_score + g_score + f_score + s_score

                rader.append({
                    "sak_id": sak.get("sak_id"),
                    "sak_adresse": sak.get("adresse"),
                    "sakstype": sak.get("sakstype"),
                    "saksdato": sak.get("saksdato"),
                    "organisasjonsnummer": bedrift.get("organisasjonsnummer"),
                    "bedrift_navn": bedrift.get("navn"),
                    "bransje": bedrift.get("bransje"),
                    "epost": bedrift.get("epost"),
                    "telefon": bedrift.get("telefon"),
                    "score": round(score, 1),
                    # Ekstra kolonner (transparens/feilsøking) - kjernekolonnene over er uendret.
                    "matchet_nace": nace,
                    "antall_bransjer_i_sak": antall_bransjer,
                    "delscore_bransje": round(b_score, 1),
                    "delscore_geografi": round(g_score, 1),
                    "delscore_ferskhet": round(f_score, 1),
                    "delscore_storrelse": round(s_score, 1),
                })

    MATCH_KOLONNER = [
        "sak_id", "sak_adresse", "sakstype", "saksdato", "organisasjonsnummer",
        "bedrift_navn", "bransje", "epost", "telefon", "score",
        "matchet_nace", "antall_bransjer_i_sak",
        "delscore_bransje", "delscore_geografi", "delscore_ferskhet", "delscore_storrelse",
    ]
    if not rader:
        return pd.DataFrame(columns=MATCH_KOLONNER)

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
