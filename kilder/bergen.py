"""Kilde-adapter for Bergen kommunes saksinnsyn-API.

Verifisert: robots.txt for bergen.kommune.no blokkerer kun
/innsynplanogbyggesak/api/fil/* og /innsynplanogbyggesak/api/saksgang -
selve søke-API-et (/api/saker) er ikke omfattet, og er det eneste vi skraper.

Trondheim (trondheim.innsynsportal.no) og Oslo PBE
(innsyn.pbe.oslo.kommune.no) er UTELUKKET - begge har robots.txt
"Disallow: /" og skal ikke skrapes.

VIKTIG (personvern): "tiltakshaver" (navnet på privatpersonen som søker) er en
personopplysning og leses ALDRI ut / lagres aldri. Feltet "soker" (ansvarlig
søker) leses KUN for å utlede én boolean - `profesjonell_soker` (ser søkeren ut
som et foretak, ja/nei) - via base.er_profesjonell_soker. Selve navnet lagres
aldri; kun ja/nei-flagget havner i saker.csv. Dette er avklart og ønsket (jf.
brukerbeslutning), og holder oss innenfor personvernregelen.
"""
import time
from datetime import datetime, timezone

from kilder import base

BERGEN_API_URL = "https://www.bergen.kommune.no/innsynplanogbyggesak/api/saker"
BERGEN_SAK_URL_MAL = (
    "https://www.bergen.kommune.no/omkommunen/offentlig-innsyn/"
    "innsynplanogbyggesak/saksinnsyn/sak/{saksnr}"
)


class BergenKilde(base.Kilde):
    """Byggesak-adapter for Bergen kommune (kommunenr 4601)."""

    kommunenummer = "4601"
    kommunenavn = "Bergen"
    fylke = "Vestland"

    def fetch_saker(self, rows: int = 150, sleep_s: float = 0.3) -> list[dict]:
        """Hent de `rows` sist innkomne byggesakene fra Bergen, nyest først.

        Returnerer en liste med dict-er med nøklene i base.SAK_KOLONNER.
        Kun ekte byggesaker (saksnr starter med "BYGG-") tas med.
        """
        params = {
            "tekst": "BYGG",  # matcher saksnr-prefiks BYGG-YYYY/NNNN, dvs. alle byggesaker
            "start": 0,
            "rows": rows,
            "orderBy": "saksdato",
            "asc": "false",
        }
        resp = base.get_med_retry(BERGEN_API_URL, params)
        resp.raise_for_status()
        time.sleep(sleep_s)

        items = resp.json().get("items", [])
        rader = []
        for sak in items:
            saksnr = sak.get("saksnr")
            # Fritekstsøket "BYGG" drar også inn henvendelser (HENV-), klager (KLAGE-)
            # og tilsyn (TILSYN-) fordi ordet "bygg" står i tittelen. Det er ikke reelle
            # byggetillatelser og gir verdiløse leads - behold kun ekte byggesaker (BYGG-).
            if not (saksnr and str(saksnr).startswith("BYGG-")):
                continue
            saksdato_ms = sak.get("saksdato")
            saksdato = (
                datetime.fromtimestamp(saksdato_ms / 1000, tz=timezone.utc).date().isoformat()
                if saksdato_ms else None
            )
            adresse_liste = sak.get("adresse") or []

            rader.append(self._rad(
                sak_id=saksnr,
                postnummer=base.postnummer_fra(adresse_liste),
                adresse=base.gateadresse_fra(adresse_liste),
                saksdato=saksdato,
                sakstype=sak.get("tittel"),
                status=sak.get("status"),  # f.eks. "Under behandling" / "Avsluttet"
                # KUN boolean - navnet på søker lagres aldri (personvern, se toppen):
                profesjonell_soker=base.er_profesjonell_soker(sak.get("soker")),
                kilde_url=BERGEN_SAK_URL_MAL.format(saksnr=saksnr) if saksnr else None,
            ))

        return rader


KILDE = BergenKilde()
