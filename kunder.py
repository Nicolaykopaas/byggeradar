"""Kunderegister for den betalte leveransen (99 kr/mnd ukentlige leads).

Kilden er data/kunder.csv - en enkel CSV, ingen database (jf. CLAUDE.md).
Hvis STRIPE_SECRET_KEY finnes i .env prøver vi å berike med aktive Stripe-
abonnement, men det er HELT valgfritt: Stripe-delen feiler stille og logger bare.
CSV-en er alltid fasit.

Skjema (kolonner i data/kunder.csv):
    epost               kundens e-postadresse (unik nokkel)
    navn                navn/firma, brukes i hilsen (kan vaere tomt)
    kommunenummer       f.eks. 4601 (Bergen). Tom = ingen kommunefilter
    postnummer_prefiks  f.eks. "50" -> matcher postnr som starter paa 50. Tom = hele kommunen
    bransjer            semikolon-separert, samme navn som bedrifter.csv "bransje"
                        (f.eks. "Snekkerarbeid/tomrer;Takarbeid"). Tom = alle bransjer
    min_score           lavest tillatte matchscore 0-100
    aktiv               ja/nei (ja/true/1 = aktiv)
    opprettet           ISO-dato for naar kunden ble lagt til
"""
import os
from datetime import date

import pandas as pd

from config import PATHS, env
from logg import get_logger

log = get_logger("kunder")

# Kolonnerekkefolge i data/kunder.csv - brukes ved lesing og skriving.
KUNDE_KOLONNER = [
    "epost", "navn", "kommunenummer", "postnummer_prefiks",
    "bransjer", "min_score", "aktiv", "opprettet",
]

# Verdier i "aktiv"-kolonnen som regnes som aktiv.
_AKTIV_SANN = {"ja", "true", "1", "yes", "y", "sant"}


def _tom_ramme() -> pd.DataFrame:
    """Tom DataFrame med riktige kolonner (brukes naar fila mangler)."""
    return pd.DataFrame(columns=KUNDE_KOLONNER)


def les_kunder() -> pd.DataFrame:
    """Les data/kunder.csv. Returner tom ramme med riktige kolonner hvis fila mangler.

    Alt leses som tekst slik at ledende nuller i kommune-/postnummer bevares.
    Manglende kolonner fylles inn som tomme, slik at eldre filer ikke knekker.
    """
    sti = PATHS["kunder"]
    if not os.path.exists(sti):
        return _tom_ramme()
    try:
        df = pd.read_csv(sti, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return _tom_ramme()
    for kol in KUNDE_KOLONNER:
        if kol not in df.columns:
            df[kol] = ""
    return df[KUNDE_KOLONNER]


def _er_aktiv(verdi) -> bool:
    return isinstance(verdi, str) and verdi.strip().lower() in _AKTIV_SANN


def aktive_kunder() -> pd.DataFrame:
    """Kun kunder der aktiv-kolonnen er ja/true/1.

    Prover i tillegg aa hente aktive Stripe-abonnement som en berikelse hvis
    STRIPE_SECRET_KEY finnes. Det er valgfritt og feiler stille: kunder.csv er
    alltid kilden. Vi bruker Stripe kun til aa logge en advarsel hvis en aktiv
    CSV-kunde ikke ser ut til aa ha et aktivt abonnement.
    """
    df = les_kunder()
    if df.empty:
        return df
    aktive = df[df["aktiv"].map(_er_aktiv)].copy()

    stripe_eposter = _hent_stripe_aktive_eposter()
    if stripe_eposter is not None:
        mangler = [e for e in aktive["epost"] if e.strip().lower() not in stripe_eposter]
        if mangler:
            log.info(
                "Stripe: %d aktive abonnement funnet. %d aktiv(e) CSV-kunde(r) mangler "
                "match i Stripe (leverer likevel, CSV er fasit): %s",
                len(stripe_eposter), len(mangler), ", ".join(mangler),
            )
        else:
            log.info("Stripe: %d aktive abonnement, alle CSV-kunder har match.",
                     len(stripe_eposter))
    return aktive


def _hent_stripe_aktive_eposter():
    """Best-effort: hent e-poster med aktivt Stripe-abonnement. None ved feil/uten nokkel.

    Bruker kun requests (ingen stripe-pakke, jf. avhengighetsreglene). Returnerer
    et sett med lowercase e-poster, eller None hvis Stripe ikke er konfigurert
    eller kallet feiler. Feiler ALLTID stille - dette skal aldri stoppe leveransen.
    """
    nokkel = env("STRIPE_SECRET_KEY")
    if not nokkel:
        return None
    try:
        import requests

        eposter = set()
        # Vi trenger kundens e-post; utvid subscription med customer-objektet.
        params = {"status": "active", "limit": 100, "expand[]": "data.customer"}
        url = "https://api.stripe.com/v1/subscriptions"
        resp = requests.get(url, params=params, auth=(nokkel, ""), timeout=15)
        resp.raise_for_status()
        for sub in resp.json().get("data", []):
            kunde = sub.get("customer")
            if isinstance(kunde, dict):
                epost = kunde.get("email")
                if epost:
                    eposter.add(epost.strip().lower())
        return eposter
    except Exception as exc:  # noqa: BLE001 - Stripe skal aldri stoppe leveransen
        log.warning("Stripe-berikelse hoppet over (feilet stille): %s", exc)
        return None


def _normaliser_bransjer(bransjer) -> str:
    """Gjor bransjer om til en ren semikolon-separert streng.

    Godtar liste/tuple eller ferdig streng. Tomme biter fjernes.
    """
    if bransjer is None:
        return ""
    if isinstance(bransjer, (list, tuple, set)):
        biter = [str(b).strip() for b in bransjer if str(b).strip()]
    else:
        biter = [b.strip() for b in str(bransjer).split(";") if b.strip()]
    return ";".join(biter)


def legg_til_kunde(epost: str, kommunenummer: str = "", postnummer_prefiks: str = "",
                   bransjer="", min_score=0, navn: str = "", aktiv: str = "ja") -> pd.DataFrame:
    """Legg til ny kunde eller oppdater eksisterende (matcher paa e-post).

    Skriver hele data/kunder.csv paa nytt. Returnerer den oppdaterte rammen.
    """
    epost = (epost or "").strip()
    if not epost:
        raise ValueError("epost er paakrevd")

    df = les_kunder()
    ny_rad = {
        "epost": epost,
        "navn": (navn or "").strip(),
        "kommunenummer": str(kommunenummer or "").strip(),
        "postnummer_prefiks": str(postnummer_prefiks or "").strip(),
        "bransjer": _normaliser_bransjer(bransjer),
        "min_score": str(min_score if min_score not in (None, "") else 0).strip(),
        "aktiv": (aktiv or "ja").strip(),
        "opprettet": date.today().isoformat(),
    }

    maske = df["epost"].str.strip().str.lower() == epost.lower()
    if maske.any():
        # Behold opprinnelig opprettet-dato ved oppdatering.
        ny_rad["opprettet"] = df.loc[maske, "opprettet"].iloc[0] or ny_rad["opprettet"]
        for kol, verdi in ny_rad.items():
            df.loc[maske, kol] = verdi
        log.info("Oppdaterte kunde %s", epost)
    else:
        df = pd.concat([df, pd.DataFrame([ny_rad])], ignore_index=True)
        log.info("La til ny kunde %s", epost)

    _skriv_kunder(df)
    return df


def deaktiver_kunde(epost: str) -> bool:
    """Sett aktiv=nei for en kunde. Returnerer True hvis kunden fantes."""
    epost = (epost or "").strip()
    df = les_kunder()
    maske = df["epost"].str.strip().str.lower() == epost.lower()
    if not maske.any():
        log.warning("Fant ingen kunde med e-post %s", epost)
        return False
    df.loc[maske, "aktiv"] = "nei"
    _skriv_kunder(df)
    log.info("Deaktiverte kunde %s", epost)
    return True


def _skriv_kunder(df: pd.DataFrame):
    os.makedirs(os.path.dirname(PATHS["kunder"]), exist_ok=True)
    df[KUNDE_KOLONNER].to_csv(PATHS["kunder"], index=False)
