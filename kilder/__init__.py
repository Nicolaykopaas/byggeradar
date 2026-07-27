"""Register over kilde-adaptere. Nye kommuner plukkes opp automatisk.

Legg til en fil kilder/<kommune>.py med `KILDE = MinKilde()`, så dukker den opp
i alle_kilder() uten at noe annet må endres.
"""
import importlib
import pkgutil

from kilder.base import Kilde  # noqa: F401 (re-eksport for adaptere)

_SKIP = {"base"}


def alle_kilder() -> list:
    """Alle registrerte kilde-adaptere (én per kommune)."""
    kilder = []
    for modinfo in pkgutil.iter_modules(__path__):
        if modinfo.name in _SKIP:
            continue
        mod = importlib.import_module(f"{__name__}.{modinfo.name}")
        kilde = getattr(mod, "KILDE", None)
        if kilde is not None:
            kilder.append(kilde)
    return kilder


def kommune_info() -> dict:
    """{kommunenummer: (kommunenavn, fylke)} for alle registrerte kilder."""
    return {k.kommunenummer: (k.kommunenavn, k.fylke) for k in alle_kilder()}
