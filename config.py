"""Felles konfigurasjon og en liten .env-leser.

Vi holder oss til reglene i CLAUDE.md: kun pandas + streamlit + requests som
avhengigheter. Derfor en egen mini-parser for .env i stedet for python-dotenv.
Hemmeligheter (Stripe-nøkkel, SMTP-passord) legges i .env som IKKE spores av git.
"""
import os

# --- Kataloger og filstier -------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
UTBOKS_DIR = os.path.join(DATA_DIR, "utboks")      # salgs-e-poster som venter på godkjenning
SENDT_DIR = os.path.join(DATA_DIR, "sendt")        # arkiv over sendte salgs-e-poster
EMAIL_DRAFTS_DIR = os.path.join(DATA_DIR, "email_drafts")  # legacy: dashbord-utkast
KUNDE_UTBOKS_DIR = os.path.join(DATA_DIR, "kunde_utboks")  # ukentlige leads til betalende kunder
KUNDE_SENDT_DIR = os.path.join(DATA_DIR, "kunde_sendt")    # arkiv over leads sendt til kunder

PATHS = {
    "saker": os.path.join(DATA_DIR, "saker.csv"),
    "bedrifter": os.path.join(DATA_DIR, "bedrifter.csv"),
    "matches": os.path.join(DATA_DIR, "matches.csv"),
    "kontaktet": os.path.join(DATA_DIR, "kontaktet.csv"),
    "kunder": os.path.join(DATA_DIR, "kunder.csv"),
    "kunde_sendt": os.path.join(DATA_DIR, "kunde_sendt.csv"),  # logg: hvilke leads hver kunde har fått
}

# --- Pilot-innstillinger ---------------------------------------------------
BERGEN_KOMMUNENUMMER = "4601"


# --- .env-leser ------------------------------------------------------------
def load_env(path: str = None) -> dict:
    """Les enkle KEY=VALUE-linjer fra .env. Kommentarer (#) og tomme linjer ignoreres.

    Verdier settes i os.environ slik at de også er tilgjengelige der, men
    eksisterende miljøvariabler overskrives ikke (miljøet vinner).
    """
    path = path or os.path.join(BASE_DIR, ".env")
    verdier = {}
    if not os.path.exists(path):
        return verdier
    with open(path, "r", encoding="utf-8") as f:
        for linje in f:
            linje = linje.strip()
            if not linje or linje.startswith("#") or "=" not in linje:
                continue
            nokkel, _, verdi = linje.partition("=")
            nokkel = nokkel.strip()
            verdi = verdi.strip().strip('"').strip("'")
            verdier[nokkel] = verdi
            os.environ.setdefault(nokkel, verdi)
    return verdier


def env(nokkel: str, standard: str = None) -> str:
    """Hent en konfigverdi: miljøvariabel først, så .env, ellers standard."""
    if nokkel in os.environ:
        return os.environ[nokkel]
    return load_env().get(nokkel, standard)
