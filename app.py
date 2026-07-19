"""Streamlit-dashbord for Byggesaksradar.

Kjør: streamlit run app.py
"""
import os
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Byggesaksradar", layout="wide")
st.title("Byggesaksradar")

DATA_DIR = "data"
KONTAKTET_PATH = os.path.join(DATA_DIR, "kontaktet.csv")


@st.cache_data(ttl=60)
def last_data():
    matches = pd.read_csv(os.path.join(DATA_DIR, "matches.csv"))
    try:
        kontaktet = pd.read_csv(KONTAKTET_PATH)
    except FileNotFoundError:
        kontaktet = pd.DataFrame(columns=["organisasjonsnummer", "sak_id", "dato"])
    return matches, kontaktet


try:
    matches, kontaktet = last_data()
except FileNotFoundError:
    st.warning("Fant ikke data/matches.csv. Kjør byggesak_fetch.py, brreg_fetch.py og compute_scores.py først.")
    st.stop()

kontaktet_orgnr = set(kontaktet["organisasjonsnummer"].astype(str))

col1, col2 = st.columns(2)
with col1:
    bransjer = ["Alle"] + sorted(matches["bransje"].dropna().unique().tolist())
    valgt_bransje = st.selectbox("Bransje", bransjer)
with col2:
    min_score = st.slider("Minimum score", 0, 100, 50)

visning = matches[matches["score"] >= min_score]
if valgt_bransje != "Alle":
    visning = visning[visning["bransje"] == valgt_bransje]

visning = visning.copy()
visning["allerede_kontaktet"] = visning["organisasjonsnummer"].astype(str).isin(kontaktet_orgnr)

st.write(f"{len(visning)} matcher")
st.dataframe(visning, use_container_width=True)

st.divider()
st.subheader("Marker som kontaktet")

ukontaktet = visning[~visning["allerede_kontaktet"]]
if not ukontaktet.empty:
    valg = st.selectbox(
        "Velg match",
        ukontaktet.index,
        format_func=lambda i: f"{ukontaktet.loc[i, 'bedrift_navn']} - {ukontaktet.loc[i, 'sak_adresse']}",
    )
    if st.button("Marker som kontaktet"):
        ny_rad = pd.DataFrame([{
            "organisasjonsnummer": ukontaktet.loc[valg, "organisasjonsnummer"],
            "sak_id": ukontaktet.loc[valg, "sak_id"],
            "dato": pd.Timestamp.now().strftime("%Y-%m-%d"),
        }])
        os.makedirs(DATA_DIR, exist_ok=True)
        ny_rad.to_csv(KONTAKTET_PATH, mode="a", header=not os.path.exists(KONTAKTET_PATH), index=False)
        st.cache_data.clear()
        st.rerun()
else:
    st.info("Alle synlige matcher er allerede kontaktet.")
