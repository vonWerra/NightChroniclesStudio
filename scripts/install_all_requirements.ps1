# PowerShell helper to create/activate venv and install all requirements
param(
    [string]$venvPath = ".venv"
)

if (-not (Test-Path $venvPath)) {
    python -m venv $venvPath
}

$activate = Join-Path $venvPath "Scripts\Activate.ps1"
if (Test-Path $activate) {
    & $activate
} else {
    Write-Host "Could not find activation script at $activate"
}

Write-Host "Installing runtime requirements from requirements-all.txt"
python -m pip install --upgrade pip
python -m pip install -r requirements-all.txt

Write-Host "If you want dev/test deps, run: python -m pip install -r requirements-all-dev.txt"
