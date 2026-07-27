"""Interaktiv "Finn-feed"-prototype i Streamlit.

Kjør:  streamlit run finn_feed.py

Viser nye byggetillatelser som annonser, anonymisert til postnummer, med filtre på
fag/postnr/score. "Lås opp" er en prototype-CTA (ingen betaling). Formål: teste
verdiopplevelsen før vi bygger ekte betaling.
"""
import pandas as pd
import streamlit as st

from feed import bygg_feed_rader, ferskhet_etikett

st.set_page_config(page_title="Byggeradar – prototype", layout="wide")
st.title("Byggeradar")
st.caption("Nye byggetillatelser i Bergen – anonymisert til postnummer. Prototype: «Lås opp» er kun en demo.")

rader = bygg_feed_rader()
if not rader:
    st.warning("Ingen data. Kjør `python run_pipeline.py` først.")
    st.stop()

# --- Filtre ---
alle_bransjer = sorted({b for r in rader for b in r["bransjer"]})
alle_postnr = sorted({r["omrade"] for r in rader})
with st.sidebar:
    st.header("Filtre")
    valgt_fag = st.multiselect("Fag", alle_bransjer)
    valgt_postnr = st.multiselect("Postnummer", alle_postnr)
    min_score = st.slider("Minimum matchscore", 0, 100, 40)
    maks_dager = st.slider("Maks alder (dager)", 1, 60, 30)

def _passer(r):
    if valgt_fag and not (set(valgt_fag) & set(r["bransjer"])):
        return False
    if valgt_postnr and r["omrade"] not in valgt_postnr:
        return False
    if r["score"] < min_score:
        return False
    if r["dager_siden"] is not None and r["dager_siden"] > maks_dager:
        return False
    return True

vist = [r for r in rader if _passer(r)]
st.subheader(f"{len(vist)} ferske saker")

# --- Kort i rutenett ---
kolonner = st.columns(3)
for i, r in enumerate(vist):
    with kolonner[i % 3].container(border=True):
        topp = f"**{r['score']}** · {ferskhet_etikett(r['dager_siden'])}"
        st.markdown(topp)
        st.markdown(f"#### {r['sakstype']}")
        st.markdown(f"🔒 Område: **{r['omrade']}** · eksakt adresse skjult")
        if r["bransjer"]:
            st.markdown(" ".join(f"`{b}`" for b in r["bransjer"][:4]))
        if st.button("Lås opp full adresse – 100 kr", key=r["sak_id"]):
            st.info("Prototype: her ville full adresse + lenke til saken låses opp, eller inngå i abonnementet ditt.")
