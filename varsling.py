"""Varsling: Windows-notifikasjon + e-post via SMTP.

Bruker kun standardbiblioteket (smtplib, subprocess) + config.env, ingen nye
avhengigheter. SMTP-innstillinger leses fra .env:

    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_BRUKER=din@gmail.com
    SMTP_PASSORD=app-passord-16-tegn      # Gmail: lag "app-passord", ikke vanlig passord
    SMTP_FRA=din@gmail.com                 # valgfri, faller tilbake til SMTP_BRUKER
    VARSEL_TIL=din@gmail.com               # hvor drift-varsler sendes
"""
import smtplib
import subprocess
from email.mime.text import MIMEText
from email.utils import formataddr

from config import env
from logg import get_logger

log = get_logger("varsling")


def windows_notifikasjon(tittel: str, melding: str) -> bool:
    """Best-effort Windows toast/ballong. Returnerer True hvis kommandoen kjørte.

    Bruker System.Windows.Forms.NotifyIcon (finnes på alle Windows) slik at vi
    slipper å installere BurntToast. Feiler stille på ikke-Windows.
    """
    ps = (
        "[reflection.assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null;"
        "$n = New-Object System.Windows.Forms.NotifyIcon;"
        "$n.Icon = [System.Drawing.SystemIcons]::Warning;"
        "$n.BalloonTipTitle = $env:VARSEL_TITTEL;"
        "$n.BalloonTipText = $env:VARSEL_TEKST;"
        "$n.Visible = $true; $n.ShowBalloonTip(10000); Start-Sleep -Seconds 6; $n.Dispose()"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            env={"VARSEL_TITTEL": tittel, "VARSEL_TEKST": melding,
                 "SystemRoot": _systemroot(), "PATH": _path()},
            timeout=20, check=False,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Klarte ikke vise Windows-notifikasjon: %s", exc)
        return False


def _systemroot() -> str:
    import os
    return os.environ.get("SystemRoot", r"C:\Windows")


def _path() -> str:
    import os
    return os.environ.get("PATH", "")


def send_epost(emne: str, tekst: str, til: str = None) -> bool:
    """Send en e-post via SMTP. Returnerer True ved suksess.

    Returnerer False (og logger) hvis SMTP ikke er konfigurert, slik at
    kallende kode kan falle tilbake på annen varsling.
    """
    host = env("SMTP_HOST")
    bruker = env("SMTP_BRUKER")
    passord = env("SMTP_PASSORD")
    port = int(env("SMTP_PORT", "587"))
    fra = env("SMTP_FRA") or bruker
    til = til or env("VARSEL_TIL") or bruker

    if not (host and bruker and passord and til):
        log.info("SMTP ikke fullstendig konfigurert - hopper over e-post (emne: %s)", emne)
        return False

    # Avsender fremstår alltid som SELSKAPET (Byggeradar), aldri en privatperson.
    # Vi setter et visningsnavn, så mottaker ser "Byggeradar", ikke et personnavn.
    avsender_navn = env("AVSENDER_NAVN") or "Byggeradar"
    msg = MIMEText(tekst, _charset="utf-8")
    msg["Subject"] = emne
    msg["From"] = formataddr((avsender_navn, fra))
    msg["To"] = til

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls()
            server.login(bruker, passord)
            server.sendmail(fra, [til], msg.as_string())
        log.info("Sendte e-post til %s (emne: %s)", til, emne)
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("E-postsending feilet: %s", exc)
        return False


def varsle(tittel: str, melding: str):
    """Kombinert varsling: prøv e-post, og vis alltid Windows-notifikasjon."""
    epost_ok = send_epost(tittel, melding)
    notif_ok = windows_notifikasjon(tittel, melding[:200])
    if not (epost_ok or notif_ok):
        log.warning("Ingen varslingskanal virket. Melding: %s | %s", tittel, melding)
