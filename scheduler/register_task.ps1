# Registrerer en daglig Windows-oppgave som kjører Byggesaksradar-pipelinen.
# Kjør ÉN gang i en vanlig PowerShell (ikke som admin nødvendig for gjeldende bruker):
#
#     powershell -ExecutionPolicy Bypass -File scheduler\register_task.ps1
#
# Standard kjøretid er 07:15 hver dag. Endre med -Tid "08:00".
# Avregistrer med:  Unregister-ScheduledTask -TaskName "Byggesaksradar" -Confirm:$false

param(
    [string]$Tid = "07:15",
    [string]$OppgaveNavn = "Byggesaksradar"
)

$ErrorActionPreference = "Stop"
$Rot = Split-Path -Parent $PSScriptRoot
$Script = Join-Path $Rot "scheduler\run_daily.ps1"

if (-not (Test-Path $Script)) { throw "Fant ikke $Script" }

$Handling = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`"" `
    -WorkingDirectory $Rot

$Utloser = New-ScheduledTaskTrigger -Daily -At $Tid

# Kjør selv om maskinen er på batteri, og prøv igjen hvis den var avslått
$Innst = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $OppgaveNavn -Action $Handling -Trigger $Utloser `
    -Settings $Innst -Description "Daglig skraping, matching og scoring for Byggesaksradar" `
    -Force | Out-Null

Write-Host "Registrerte oppgaven '$OppgaveNavn' - kjører daglig kl. $Tid."

# Ukentlig helsesjekk (mandager kl. 08:00)
$VenvPy = Join-Path $Rot ".venv\Scripts\python.exe"
$HelseArg = "-NoProfile -ExecutionPolicy Bypass -Command " +
    "`"Set-Location '$Rot'; if (Test-Path '$VenvPy') { & '$VenvPy' helsesjekk.py } else { python helsesjekk.py }`""
$HelseHandling = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $HelseArg -WorkingDirectory $Rot
$HelseUtloser = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "08:00"
Register-ScheduledTask -TaskName "$OppgaveNavn-Helsesjekk" -Action $HelseHandling -Trigger $HelseUtloser `
    -Settings $Innst -Description "Ukentlig helsesjekk for Byggesaksradar" -Force | Out-Null
Write-Host "Registrerte oppgaven '$OppgaveNavn-Helsesjekk' - kjører mandager kl. 08:00."

# Ukentlig levering av leads til betalende kunder (mandager kl. 08:30).
# Samtykket leveranse til abonnenter - kan sendes automatisk.
$LeverArg = "-NoProfile -ExecutionPolicy Bypass -Command " +
    "`"Set-Location '$Rot'; if (Test-Path '$VenvPy') { & '$VenvPy' send_kunde_leads.py } else { python send_kunde_leads.py }`""
$LeverHandling = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $LeverArg -WorkingDirectory $Rot
$LeverUtloser = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "08:30"
Register-ScheduledTask -TaskName "$OppgaveNavn-Kundelevering" -Action $LeverHandling -Trigger $LeverUtloser `
    -Settings $Innst -Description "Ukentlig levering av leads til betalende kunder" -Force | Out-Null
Write-Host "Registrerte oppgaven '$OppgaveNavn-Kundelevering' - kjører mandager kl. 08:30."

# Autonom salgs-utsending som SELSKAPET (tirsdager kl. 09:00).
# Lager ferske salgs-e-poster og sender maks 10/uke (cap beskytter domene-omdømme).
# Kun upersonlige adresser (§15) + avmelding + aldri samme bedrift to ganger.
# INERT til SMTP er satt i .env - sender ingenting uten din egen sendekonto.
$SendArg = "-NoProfile -ExecutionPolicy Bypass -Command " +
    "`"Set-Location '$Rot'; `$py = if (Test-Path '$VenvPy') { '$VenvPy' } else { 'python' }; " +
    "& `$py generate_email_drafts.py --utboks; & `$py approve_and_send.py --maks 10`""
$SendHandling = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $SendArg -WorkingDirectory $Rot
$SendUtloser = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday -At "09:00"
Register-ScheduledTask -TaskName "$OppgaveNavn-Utsending" -Action $SendHandling -Trigger $SendUtloser `
    -Settings $Innst -Description "Autonom salgs-utsending som selskapet (maks 10/uke)" -Force | Out-Null
Write-Host "Registrerte oppgaven '$OppgaveNavn-Utsending' - kjører tirsdager kl. 09:00 (inert til SMTP er satt)."

Write-Host ""
Write-Host "Test daglig-jobben nå med:  Start-ScheduledTask -TaskName '$OppgaveNavn'"
Write-Host "Se status med:               Get-ScheduledTaskInfo -TaskName '$OppgaveNavn'"
