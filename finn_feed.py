"""Byggeradar - interaktiv «Din radar» i Streamlit.

Kjør:  streamlit run finn_feed.py

Kuraterer nye byggesaker ned til de som er verdt tiden din, filtrert på ditt fag
og område. Postnr-anonymisert, ingen personopplysninger. Ærlig handlingstips per
prosjekt (ingen falsk betalingsmur foran offentlig info).
"""
import streamlit as st

import kunder
from feed import bygg_feed_rader, ferskhet_etikett
from radar import bygg_radar, ukesammendrag

st.set_page_config(page_title="Byggeradar", layout="wide")
st.title("Byggeradar")
st.caption("Vi leser hver nye byggetillatelse i hele Norge så du slipper. Her er de som er verdt tiden din.")

_alle = bygg_feed_rader()
if not _alle:
    st.warning("Ingen data. Kjør `python run_pipeline.py` først.")
    st.stop()

alle_fag = sorted({b for r in _alle for b in r["bransjer"]})
alle_fylker = sorted({r["fylke"] for r in _alle if r.get("fylke")})
alle_postnr = sorted({r["postnummer"] for r in _alle if r.get("postnummer")})
# (fylke, kommunenavn, kommunenummer) - navn vises, nummer filtrerer vi på
kommune_trip = sorted({(r["fylke"], r["kommunenavn"], r["kommunenummer"])
                       for r in _alle if r.get("kommunenavn") and r.get("kommunenummer")})

with st.sidebar:
    st.header("Din radar")
    fag = st.multiselect("Ditt fag", alle_fag)
    valgt_fylke = st.selectbox("Fylke", ["Hele Norge"] + alle_fylker)
    # Kommune-listen kaskaderer på valgt fylke
    kommuner = [(navn, nr) for (fyl, navn, nr) in kommune_trip
                if valgt_fylke == "Hele Norge" or fyl == valgt_fylke]
    kommune_navn = st.selectbox("Kommune", ["Alle kommuner"] + [navn for navn, _ in kommuner])
    omrade = st.selectbox("Område (postnr)", ["Alle postnr"] + alle_postnr)
    min_mulighet = st.slider("Minimum mulighet", 0, 100, 40)
    maks_dager = st.slider("Maks alder (dager)", 1, 60, 30)
    skjul_tatt = st.checkbox("Skjul tidlige/trolig tatte", value=True)
    kun_ledig = st.checkbox("Kun trolig ledige (privat søker)", value=False)
    st.caption("«Mulighet» = ferskt + stort + treffer ditt fag.")

fylke = None if valgt_fylke == "Hele Norge" else valgt_fylke
knr_map = {navn: nr for navn, nr in kommuner}
kommunenummer = knr_map.get(kommune_navn)  # None ved "Alle kommuner"
prefiks = "" if omrade == "Alle postnr" else omrade
rader = bygg_radar(fag=fag or None, omrade_prefiks=prefiks,
                   min_mulighet=min_mulighet, maks_dager=maks_dager,
                   kommunenummer=kommunenummer, fylke=fylke)
if skjul_tatt:
    rader = [r for r in rader if r["tilgjengelighet"]["niva"] == "uavklart"]
if kun_ledig:
    rader = [r for r in rader if r.get("profesjonell_soker") is False]
s = ukesammendrag(rader)

k = st.columns(4)
k[0].metric("Aktuelle prosjekter", s["totalt"])
k[1].metric("Trolig ledige", s["trolig_ledige"])
k[2].metric("Nye siste 7 dager", s["ferske_7d"])
k[3].metric("Store prosjekter", s["store"])

# --- Fangst-trakt: la interesserte melde seg på ukentlig varsel ---
with st.expander("Få ukentlig varsel på e-post, gratis å komme i gang"):
    with st.form("varsle_meg"):
        e = st.text_input("Din e-post (helst firmapost@…)")
        c1, c2 = st.columns(2)
        valgt_fag = c1.multiselect("Fag du vil ha varsel om", alle_fag, default=fag)
        valgt_postnr = c2.text_input("Postnr-område (valgfritt, f.eks. 52)", value=prefiks)
        sendt = st.form_submit_button("Meld meg på")
    if sendt:
        if not e or "@" not in e:
            st.error("Skriv inn en gyldig e-postadresse.")
        else:
            kunder.legg_til_kunde(
                epost=e.strip(), kommunenummer=kommunenummer or "4601",
                postnummer_prefiks=valgt_postnr.strip(),
                bransjer=";".join(valgt_fag), min_score=40, aktiv="interessent")
            st.success("Takk! Du er registrert som interessent. Vi tar kontakt før første utsending.")
st.divider()

if not rader:
    st.info("Ingen prosjekter med gjeldende filter. Prøv å senke «minimum mulighet» eller utvide området.")
    st.stop()

SKALA_EMOJI = {"stor": "", "middels": "", "liten": ""}
kol = st.columns(3)
for i, r in enumerate(rader):
    with kol[i % 3].container(border=True):
        st.markdown(f"**{r['mulighet']}** · {SKALA_EMOJI[r['skala']]} {r['skala_etikett']} · {ferskhet_etikett(r['dager_siden'])}")
        st.markdown(f"#### {r['sakstype']}")
        sted = f"{r['kommunenavn']} · Postnr **{r['omrade']}**" if r.get("kommunenavn") else f"Postnr **{r['omrade']}**"
        linje = f"{sted}"
        if r.get("status"):
            linje += f" · {r['status']}"
        st.markdown(linje)
        if r["bransjer"]:
            st.markdown(" ".join(f"`{b}`" for b in r["bransjer"][:4]))
        a = r["arbeid"]
        if a["oppgaver"]:
            st.markdown(f"**Arbeid som inngår:** {a['overskrift']}")
            st.markdown("\n".join(f"- {o}" for o in a["oppgaver"]))
        else:
            st.caption(a["overskrift"])
        tg = r["tilgjengelighet"]
        boks = {"tatt": st.error, "tidlig": st.warning, "uavklart": st.info}[tg["niva"]]
        boks(f"**{tg['etikett']}**, {tg['forklaring']}")
        if tg["niva"] == "uavklart":
            st.caption(f"{r['tips']}")
        if r.get("kilde_url"):
            st.markdown(f"[Se saken hos kommunen]({r['kilde_url']})")
