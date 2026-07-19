"""Streamlit-dashbord for Byggesaksradar.

Kjør: streamlit run app.py
"""
import os
import pandas as pd
import streamlit as st

from generate_email_drafts import trygg_filnavn

st.set_page_config(page_title="Byggesaksradar", layout="wide")
st.title("Byggesaksradar")

DATA_DIR = "data"
EMAIL_DIR = os.path.join(DATA_DIR, "email_drafts")
PATHS = {
    "saker": os.path.join(DATA_DIR, "saker.csv"),
    "bedrifter": os.path.join(DATA_DIR, "bedrifter.csv"),
    "matches": os.path.join(DATA_DIR, "matches.csv"),
    "kontaktet": os.path.join(DATA_DIR, "kontaktet.csv"),
}


@st.cache_data(ttl=60)
def last_csv(path: str, dtype=None):
    if not os.path.exists(path):
        return None
    return pd.read_csv(path, dtype=dtype)


matches = last_csv(PATHS["matches"], dtype={"organisasjonsnummer": str, "sak_id": str})
if matches is None:
    st.warning(
        "Fant ikke data/matches.csv. Kjør byggesak_fetch.py, brreg_fetch.py og "
        "compute_scores.py først for å generere data."
    )
    st.stop()

saker = last_csv(PATHS["saker"], dtype={"sak_id": str, "kommunenummer": str, "postnummer": str})
bedrifter = last_csv(PATHS["bedrifter"], dtype={"organisasjonsnummer": str, "kommunenummer": str, "postnummer": str})
kontaktet = last_csv(PATHS["kontaktet"], dtype={"organisasjonsnummer": str, "sak_id": str})
if kontaktet is None:
    kontaktet = pd.DataFrame(columns=["organisasjonsnummer", "sak_id", "dato"])

if saker is None:
    st.info("Fant ikke data/saker.csv - noe detaljinformasjon om byggesaker vil mangle.")
if bedrifter is None:
    st.info("Fant ikke data/bedrifter.csv - noe bedriftsinformasjon vil mangle.")

# Berik matches med kommune/adresse/ansatte fra bedrifter og kilde-url fra saker.
# bedrifter kan ha flere rader per org.nr (én per bransje) - dedupe før merge
# for å unngå at matches-tabellen dupliseres (fan-out på merge-nøkkelen).
if bedrifter is not None:
    bedrift_info = (
        bedrifter[["organisasjonsnummer", "kommune", "adresse", "poststed", "antall_ansatte", "hjemmeside"]]
        .drop_duplicates(subset="organisasjonsnummer")
        .rename(columns={"adresse": "bedrift_adresse"})
    )
    matches = matches.merge(bedrift_info, on="organisasjonsnummer", how="left")
if saker is not None:
    matches = matches.merge(
        saker[["sak_id", "kilde_url", "postnummer"]].rename(columns={"postnummer": "sak_postnummer"}),
        on="sak_id", how="left",
    )

kontaktet_orgnr = set(kontaktet["organisasjonsnummer"].astype(str)) if not kontaktet.empty else set()
kontaktet_par = set(zip(kontaktet.get("sak_id", []), kontaktet.get("organisasjonsnummer", [])))
matches["status"] = matches.apply(
    lambda r: "Kontaktet" if (str(r["sak_id"]), str(r["organisasjonsnummer"])) in kontaktet_par else "Ikke kontaktet",
    axis=1,
)

# --- Nøkkeltall ---
nye_saker_7d = 0
if saker is not None and "saksdato" in saker.columns:
    dato = pd.to_datetime(saker["saksdato"], errors="coerce", utc=True)
    nye_saker_7d = int((dato >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7)).sum())

ukontaktet_over_70 = int(((matches["score"] > 70) & (matches["status"] == "Ikke kontaktet")).sum())

kpi1, kpi2 = st.columns(2)
kpi1.metric("Nye saker siste 7 dager", nye_saker_7d)
kpi2.metric("Ukontaktede matcher over score 70", ukontaktet_over_70)

st.divider()

# --- Sidebar-filtre ---
st.sidebar.header("Filtre")

if "kommune" in matches.columns and matches["kommune"].notna().any():
    kommuner = ["Alle"] + sorted(matches["kommune"].dropna().unique().tolist())
    valgt_kommune = st.sidebar.selectbox("Kommune", kommuner)
else:
    valgt_kommune = "Alle"

bransjer = ["Alle"] + sorted(matches["bransje"].dropna().unique().tolist())
valgt_bransje = st.sidebar.selectbox("Bransje", bransjer)

min_score = st.sidebar.slider("Minimum score", 0, 100, 50)
skjul_kontaktede = st.sidebar.checkbox("Skjul allerede kontaktede", value=True)

visning = matches[matches["score"] >= min_score].copy()
if valgt_kommune != "Alle":
    visning = visning[visning["kommune"] == valgt_kommune]
if valgt_bransje != "Alle":
    visning = visning[visning["bransje"] == valgt_bransje]
if skjul_kontaktede:
    visning = visning[visning["status"] == "Ikke kontaktet"]

visning = visning.sort_values("score", ascending=False)

# --- Hovedtabell ---
st.subheader(f"Matcher ({len(visning)})")
visning_kolonner = {
    "bedrift_navn": "Bedrift",
    "sakstype": "Sakstype",
    "sak_adresse": "Adresse",
    "score": "Score",
    "status": "Status",
}
st.dataframe(
    visning[list(visning_kolonner.keys())].rename(columns=visning_kolonner),
    width="stretch",
    hide_index=True,
)

st.divider()

# --- Detaljvisning ---
st.subheader("Detaljer og oppfølging")

if visning.empty:
    st.info("Ingen matcher med gjeldende filter.")
else:
    valg = st.selectbox(
        "Velg match",
        visning.index,
        format_func=lambda i: f"{visning.loc[i, 'bedrift_navn']} — {visning.loc[i, 'sak_adresse']} (score {visning.loc[i, 'score']})",
    )
    rad = visning.loc[valg]

    detalj_col1, detalj_col2 = st.columns(2)
    with detalj_col1:
        st.markdown("**Byggesak**")
        st.write(f"Adresse: {rad.get('sak_adresse', '-')}")
        st.write(f"Sakstype: {rad.get('sakstype', '-')}")
        st.write(f"Dato: {rad.get('saksdato', '-')}")
        if pd.notna(rad.get("kilde_url")):
            st.write(f"Kilde: {rad['kilde_url']}")

    with detalj_col2:
        st.markdown("**Bedrift**")
        st.write(f"Navn: {rad.get('bedrift_navn', '-')}")
        st.write(f"Bransje: {rad.get('bransje', '-')}")
        st.write(f"Org.nr: {rad.get('organisasjonsnummer', '-')}")
        if pd.notna(rad.get("bedrift_adresse")):
            st.write(f"Adresse: {rad['bedrift_adresse']}, {rad.get('poststed', '')}")
        if pd.notna(rad.get("antall_ansatte")):
            st.write(f"Ansatte: {int(rad['antall_ansatte'])}")
        st.write(f"E-post: {rad.get('epost', '-') or '-'}")
        st.write(f"Telefon: {rad.get('telefon', '-') or '-'}")

    st.markdown("**E-postutkast**")
    filnavn = f"{trygg_filnavn(str(rad['sak_id']))}_{trygg_filnavn(str(rad['organisasjonsnummer']))}.txt"
    filsti = os.path.join(EMAIL_DIR, filnavn)
    if os.path.exists(filsti):
        with open(filsti, "r", encoding="utf-8") as f:
            utkast = f.read()
        st.code(utkast, language=None)
    else:
        st.info("Ingen e-postutkast generert for denne matchen ennå. Kjør generate_email_drafts.py.")

    if rad["status"] == "Kontaktet":
        st.success("Allerede markert som kontaktet.")
    elif st.button("Marker som kontaktet"):
        ny_rad = pd.DataFrame([{
            "organisasjonsnummer": rad["organisasjonsnummer"],
            "sak_id": rad["sak_id"],
            "dato": pd.Timestamp.now().strftime("%Y-%m-%d"),
        }])
        os.makedirs(DATA_DIR, exist_ok=True)
        ny_rad.to_csv(PATHS["kontaktet"], mode="a", header=not os.path.exists(PATHS["kontaktet"]), index=False)
        st.cache_data.clear()
        st.rerun()
