"""Selvtest: verifiserer at siste pipeline-kjøring gikk bra, og varsler ved feil.

Kjøres av Task Scheduler like etter run_pipeline.py. Sjekker:
  1. at data/pipeline_status.json finnes og er fersk (< MAKS_ALDER_TIMER gammel)
  2. at status["ok"] er True
  3. at kjernefilene finnes og ikke er tomme

Ved problem: skriver logs/selftest_alert.txt og sender varsel (e-post + Windows-notif).
Exit-kode 0 = alt ok, 1 = problem oppdaget.

Bruk: python selftest.py
"""
import json
import os
import sys
from datetime import datetime, timezone

from config import DATA_DIR, LOG_DIR, PATHS
from logg import get_logger
from varsling import varsle

log = get_logger("selftest")
STATUS_FIL = os.path.join(DATA_DIR, "pipeline_status.json")
ALERT_FIL = os.path.join(LOG_DIR, "selftest_alert.txt")
MAKS_ALDER_TIMER = 26  # daglig kjøring + litt slingringsmonn


def sjekk() -> list[str]:
    """Returnerer en liste med problemer. Tom liste = alt ok."""
    problemer = []

    if not os.path.exists(STATUS_FIL):
        problemer.append("data/pipeline_status.json mangler - pipeline har aldri kjørt ferdig.")
        return problemer

    try:
        with open(STATUS_FIL, "r", encoding="utf-8") as f:
            status = json.load(f)
    except Exception as exc:  # noqa: BLE001
        problemer.append(f"Klarte ikke lese pipeline_status.json: {exc}")
        return problemer

    # Ferskhet
    ferdig = status.get("ferdig")
    if ferdig:
        alder_t = (datetime.now(timezone.utc) - datetime.fromisoformat(ferdig)).total_seconds() / 3600
        if alder_t > MAKS_ALDER_TIMER:
            problemer.append(
                f"Siste kjøring er {alder_t:.0f} timer gammel (> {MAKS_ALDER_TIMER}t). "
                "Kjører den planlagte oppgaven?"
            )
    else:
        problemer.append("pipeline_status.json mangler tidsstempel 'ferdig'.")

    # Resultat
    if not status.get("ok"):
        problemer.append(f"Pipeline rapporterte feil: {status.get('feil', 'ukjent')}")

    # Kjernefiler
    for navn in ("saker", "bedrifter", "matches"):
        sti = PATHS[navn]
        if not os.path.exists(sti):
            problemer.append(f"Mangler datafil: {os.path.basename(sti)}")
        elif os.path.getsize(sti) < 20:  # bare header eller tom
            problemer.append(f"Datafil ser tom ut: {os.path.basename(sti)}")

    return problemer


def main() -> int:
    problemer = sjekk()
    if not problemer:
        log.info("Selvtest OK - alt ser bra ut.")
        if os.path.exists(ALERT_FIL):
            os.remove(ALERT_FIL)  # rydd bort gammelt varsel
        return 0

    tekst = "Byggesaksradar - pipeline trenger tilsyn:\n\n" + "\n".join(f"- {p}" for p in problemer)
    log.error(tekst)
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(ALERT_FIL, "w", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()}\n\n{tekst}\n")
    varsle("Byggesaksradar: pipeline feilet", tekst)
    return 1


if __name__ == "__main__":
    sys.exit(main())
