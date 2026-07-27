"""Godkjenn og send salgs-e-postene i data/utboks/ – med ÉN kommando.

Å kjøre dette scriptet ER godkjenningen. Det sender hver e-post i utboksen via
SMTP, logger bedriften i data/kontaktet.csv (så vi aldri kontakter samme bedrift
to ganger), og flytter den sendte fila til data/sendt/.

    python approve_and_send.py --dry-run   # vis hva som VILLE blitt sendt (sender ingenting)
    python approve_and_send.py             # send alt i utboksen
    python approve_and_send.py --maks 5    # send maks 5 (f.eks. for å teste forsiktig)

SMTP-innstillinger leses fra .env (se varsling.py). Uten dem gjør --dry-run alt
du trenger for å se innholdet, men faktisk sending krever konfigurert SMTP.
"""
import os
import shutil
import sys
from datetime import date

import pandas as pd

from config import PATHS, SENDT_DIR, UTBOKS_DIR
from logg import get_logger
from varsling import send_epost

log = get_logger("send")
MANIFEST = os.path.join(UTBOKS_DIR, "_manifest.csv")


def _parse_epost(sti: str) -> tuple[str, str, str]:
    """Les en utboks-fil: returnér (til, emne, brødtekst)."""
    with open(sti, "r", encoding="utf-8") as f:
        linjer = f.read().splitlines()
    til = emne = ""
    body_start = 0
    for i, linje in enumerate(linjer):
        if linje.startswith("To:"):
            til = linje[3:].strip()
        elif linje.startswith("Subject:"):
            emne = linje[8:].strip()
        elif linje.strip() == "":
            body_start = i + 1
            break
    body = "\n".join(linjer[body_start:]).strip()
    return til, emne, body


def _logg_kontaktet(orgnr: str, sak_id: str):
    ny = pd.DataFrame([{
        "organisasjonsnummer": orgnr,
        "sak_id": sak_id,
        "dato": date.today().isoformat(),
        "kanal": "epost-salg",
    }])
    finnes = os.path.exists(PATHS["kontaktet"])
    ny.to_csv(PATHS["kontaktet"], mode="a", header=not finnes, index=False)


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    maks = None
    if "--maks" in sys.argv:
        maks = int(sys.argv[sys.argv.index("--maks") + 1])

    if not os.path.exists(MANIFEST):
        print(f"Ingen utboks funnet ({MANIFEST}). Kjør først:")
        print("  python generate_email_drafts.py --utboks")
        return 1

    full_manifest = pd.read_csv(MANIFEST, dtype={"organisasjonsnummer": str, "sak_id": str})
    if full_manifest.empty:
        print("Utboksen er tom - ingenting å sende.")
        return 0

    # --maks begrenser hvor mange vi behandler nå, men de resterende radene skal
    # bevares i manifestet (ellers blir de foreldreløse).
    arbeidssett = full_manifest.head(maks) if maks is not None else full_manifest

    os.makedirs(SENDT_DIR, exist_ok=True)
    print(f"{'[TØRRKJØRING] ' if dry_run else ''}{len(arbeidssett)} e-post(er) behandles "
          f"(av {len(full_manifest)} i utboksen):\n")

    sendt = feilet = 0
    sendte_filer = set()  # filer som faktisk gikk ut og skal fjernes fra manifestet

    for _, rad in arbeidssett.iterrows():
        sti = os.path.join(UTBOKS_DIR, rad["fil"])
        if not os.path.exists(sti):
            log.warning("Fil mangler, hopper over: %s", rad["fil"])
            continue
        til, emne, body = _parse_epost(sti)
        print(f"  -> {rad['bedrift_navn']} <{til}>: {emne}")

        if dry_run:
            continue

        if send_epost(emne, body, til=til):
            _logg_kontaktet(str(rad["organisasjonsnummer"]), str(rad.get("sak_id", "")))
            shutil.move(sti, os.path.join(SENDT_DIR, rad["fil"]))
            sendte_filer.add(rad["fil"])
            sendt += 1
        else:
            feilet += 1

    # Behold alt som ikke ble sendt (både feilede og de vi ikke rørte pga --maks)
    if not dry_run:
        gjenstaaende = full_manifest[~full_manifest["fil"].isin(sendte_filer)]
        gjenstaaende.to_csv(MANIFEST, index=False)
        print(f"\nSendte {sendt}, feilet {feilet}. Sendte filer arkivert i {SENDT_DIR}/")
        if feilet:
            print("Feilede ligger igjen i utboksen. Sjekk SMTP-innstillinger i .env.")
    else:
        print("\nTørrkjøring - ingenting ble sendt. Fjern --dry-run for å sende.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
