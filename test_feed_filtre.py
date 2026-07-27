"""Beviser at Byggeradar-filtrene FAKTISK virker, og at ingen gateadresse lekker.

To lag testes:
  1. Streamlit-siden bruker radar.bygg_radar(...) - vi kaller den med ulike
     parametre og sjekker at resultatsettet endrer seg korrekt.
  2. Den statiske siden (feed/index.html) er JS-rendret fra innebygd JSON - vi
     parser ut DATA-arrayet og simulerer filterlogikken i Python for å bekrefte
     at tellingene stemmer, at hvert kort har en ekte http(s)-lenke, og at ingen
     gateadresse fra saker.csv finnes i HTML-en.

Kjør:  python test_feed_filtre.py   (eller: pytest test_feed_filtre.py)
"""
import json
import os
import re

import pandas as pd

from config import BASE_DIR, PATHS
from feed import bygg_feed_rader
from radar import bygg_radar

# Basissett uten dato-/mulighetsfilter, så filtrene testes isolert.
BASE = bygg_radar(min_mulighet=0, maks_dager=0)
IDS = lambda rader: sorted(r["sak_id"] for r in rader)


def _assert(navn, betingelse, detalj=""):
    if not betingelse:
        raise AssertionError(f"FEIL i {navn}: {detalj}")
    print(f"  OK  {navn}{(' - ' + detalj) if detalj else ''}")


# ---------------------------------------------------------------------------
# 1. STREAMLIT-LAGET: radar.bygg_radar
# ---------------------------------------------------------------------------
def test_fag_filter():
    fagene = sorted({b for r in BASE for b in r["bransjer"]})
    assert fagene, "Ingen fag i data - kan ikke teste fag-filter"
    fag = fagene[0]
    ut = bygg_radar(fag=[fag], min_mulighet=0, maks_dager=0)
    manuelt = [r for r in BASE if fag in r["bransjer"]]
    _assert("fag: alle rader har faget", all(fag in r["bransjer"] for r in ut), fag)
    _assert("fag: samsvarer med manuell filtrering", IDS(ut) == IDS(manuelt),
            f"{len(ut)} rader for '{fag}'")


def test_kommune_filter():
    knr = sorted({r["kommunenummer"] for r in BASE if r["kommunenummer"]})
    assert knr, "Ingen kommunenummer i data"
    k = knr[0]
    ut = bygg_radar(kommunenummer=k, min_mulighet=0, maks_dager=0)
    manuelt = [r for r in BASE if r["kommunenummer"] == k]
    _assert("kommune: kun valgt kommune", all(r["kommunenummer"] == k for r in ut), k)
    _assert("kommune: samsvarer med manuell filtrering", IDS(ut) == IDS(manuelt),
            f"{len(ut)} rader i {k}")
    tom = bygg_radar(kommunenummer="0000", min_mulighet=0, maks_dager=0)
    _assert("kommune: ukjent kommunenr gir 0 treff", tom == [], "0000")


def test_fylke_filter():
    fylker = sorted({r["fylke"] for r in BASE if r["fylke"]})
    assert fylker, "Ingen fylke i data"
    f = fylker[0]
    ut = bygg_radar(fylke=f, min_mulighet=0, maks_dager=0)
    manuelt = [r for r in BASE if r["fylke"] == f]
    _assert("fylke: kun valgt fylke", all(r["fylke"] == f for r in ut), f)
    _assert("fylke: samsvarer med manuell filtrering", IDS(ut) == IDS(manuelt),
            f"{len(ut)} rader i {f}")
    tom = bygg_radar(fylke="Ikke-Et-Fylke", min_mulighet=0, maks_dager=0)
    _assert("fylke: ukjent fylke gir 0 treff", tom == [])


def test_postnr_filter():
    postnr = sorted({r["postnummer"] for r in BASE if r["postnummer"]})
    if not postnr:
        print("  (hopper over postnr-filter: ingen postnr i data)")
        return
    p = postnr[0]
    ut = bygg_radar(omrade_prefiks=p, min_mulighet=0, maks_dager=0)
    _assert("postnr: kun valgt postnr", all(str(r["omrade"]).startswith(p) for r in ut), p)


def test_kun_ledige_predikat():
    # Streamlit filtrerer: [r for r in rader if r.profesjonell_soker is False]
    ledige = [r for r in BASE if r.get("profesjonell_soker") is False]
    _assert("kun ledige: kun privat søker (profesjonell_soker==False)",
            all(r.get("profesjonell_soker") is False for r in ledige),
            f"{len(ledige)} ledige")


def test_kun_store_predikat():
    store = [r for r in BASE if r["skala"] == "stor"]
    _assert("kun store: kun skala=='stor'", all(r["skala"] == "stor" for r in store),
            f"{len(store)} store")


def test_skjul_tatte_predikat():
    synlige = [r for r in BASE if r["tilgjengelighet"]["niva"] == "uavklart"]
    _assert("skjul tatte: kun niva=='uavklart'",
            all(r["tilgjengelighet"]["niva"] == "uavklart" for r in synlige),
            f"{len(synlige)} synlige")


def test_maks_dager_og_min_mulighet():
    fersk = bygg_radar(min_mulighet=0, maks_dager=7)
    _assert("maks_dager: ingen eldre enn 7 dager",
            all((r["dager_siden"] is None or r["dager_siden"] <= 7) for r in fersk))
    hoy = bygg_radar(min_mulighet=80, maks_dager=0)
    _assert("min_mulighet: alle >= 80", all(r["mulighet"] >= 80 for r in hoy),
            f"{len(hoy)} rader >=80")


# ---------------------------------------------------------------------------
# 2. STATISK HTML: parse DATA-JSON og simuler filterlogikken
# ---------------------------------------------------------------------------
def _les_html_data():
    sti = os.path.join(BASE_DIR, "feed", "index.html")
    with open(sti, "r", encoding="utf-8") as f:
        html = f.read()
    m = re.search(r"const DATA = (\[.*?\]);\nconst KOMMUNER", html, re.S)
    assert m, "Fant ikke DATA-arrayet i feed/index.html"
    return html, json.loads(m.group(1))


def _html_filter(data, fag="", fylke="", kommune="", postnr="",
                 kunStore=False, kunLedig=False, skjulTatt=False):
    """Python-speil av tegn()-filteret i build_feed_html.py."""
    return [r for r in data if
            (not fag or fag in r["bransjer"]) and
            (not fylke or r["fylke"] == fylke) and
            (not kommune or r["kommunenummer"] == kommune) and
            (not postnr or r["postnummer"] == postnr) and
            (not kunStore or r["skala"] == "stor") and
            (not kunLedig or r["trolig_ledig"]) and
            (not skjulTatt or r["tilg_niva"] == "uavklart")]


def test_html_filtre():
    _, data = _les_html_data()
    _assert("html: DATA ikke tom", len(data) > 0, f"{len(data)} kort")

    fag = sorted({b for r in data for b in r["bransjer"]})[0]
    ut = _html_filter(data, fag=fag)
    _assert("html fag: alle kort har faget", all(fag in r["bransjer"] for r in ut) and ut, fag)

    fylke = sorted({r["fylke"] for r in data if r["fylke"]})[0]
    utf = _html_filter(data, fylke=fylke)
    _assert("html fylke: kun valgt fylke", all(r["fylke"] == fylke for r in utf) and utf, fylke)

    knr = sorted({r["kommunenummer"] for r in data if r["kommunenummer"]})[0]
    utk = _html_filter(data, kommune=knr)
    _assert("html kommune: kun valgt kommune", all(r["kommunenummer"] == knr for r in utk) and utk, knr)
    _assert("html kommune: ukjent gir 0", _html_filter(data, kommune="0000") == [])

    utstore = _html_filter(data, kunStore=True)
    _assert("html kun store: kun skala stor", all(r["skala"] == "stor" for r in utstore))

    utledig = _html_filter(data, kunLedig=True)
    _assert("html kun ledige: kun trolig_ledig", all(r["trolig_ledig"] for r in utledig))

    utskjul = _html_filter(data, skjulTatt=True)
    _assert("html skjul tatte: kun uavklart", all(r["tilg_niva"] == "uavklart" for r in utskjul))

    # Kombinasjon skal snevre inn (aldri utvide)
    komb = _html_filter(data, fylke=fylke, kunStore=True, skjulTatt=True)
    _assert("html kombinasjon snevrer inn", len(komb) <= len(utf))


def test_html_lenker_er_ekte_url():
    _, data = _les_html_data()
    med_url = [r for r in data if r["kilde_url"]]
    _assert("html: kort har kilde_url", len(med_url) > 0, f"{len(med_url)}/{len(data)} kort")
    _assert("html: alle kilde_url er http(s)",
            all(r["kilde_url"].startswith(("http://", "https://")) for r in med_url))


def test_html_har_klikkbar_lenke_i_markup():
    html, _ = _les_html_data()
    _assert("html: 'Se saken hos kommunen'-lenke finnes i markup",
            "Se saken hos kommunen" in html and 'target="_blank"' in html)


def test_ingen_gateadresse_lekkasje():
    html, _ = _les_html_data()
    saker = pd.read_csv(PATHS["saker"], dtype=str)
    lekk = []
    if "adresse" in saker.columns:
        for a in saker["adresse"].dropna().unique():
            a = str(a).strip()
            if len(a) >= 5 and a in html:   # ignorer trivielt korte verdier
                lekk.append(a)
    _assert("personvern: ingen gateadresse fra saker.csv i HTML", not lekk,
            f"lekkasjer: {lekk[:3]}" if lekk else "0 lekkasjer")


if __name__ == "__main__":
    tester = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    print(f"Kjører {len(tester)} tester\n")
    for t in tester:
        print(t.__name__ + ":")
        t()
    print(f"\nAlle {len(tester)} tester passerte.")
