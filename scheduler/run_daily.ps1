# Daglig kjøring av Byggesaksradar-pipelinen.
# Kalles av den planlagte oppgaven (se register_task.ps1) eller manuelt.
# Kjører pipeline + selvtest, og lar exit-koden reflektere om noe feilet.

$ErrorActionPreference = "Stop"

# Rot = mappen over dette scriptet (scheduler\ -> prosjektrot)
$Rot = Split-Path -Parent $PSScriptRoot
Set-Location $Rot

# Bruk venv-python hvis det finnes, ellers python fra PATH
$VenvPy = Join-Path $Rot ".venv\Scripts\python.exe"
if (Test-Path $VenvPy) { $Py = $VenvPy } else { $Py = "python" }

Write-Host "[$(Get-Date -Format s)] Starter pipeline ..."
& $Py run_pipeline.py
$PipelineKode = $LASTEXITCODE

Write-Host "[$(Get-Date -Format s)] Kjører selvtest ..."
& $Py selftest.py
$SelftestKode = $LASTEXITCODE

if ($PipelineKode -ne 0 -or $SelftestKode -ne 0) {
    Write-Host "FEIL: pipeline=$PipelineKode selftest=$SelftestKode (se logs\)"
    exit 1
}
Write-Host "[$(Get-Date -Format s)] Ferdig OK"
exit 0
