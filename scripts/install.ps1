# Cria um ambiente virtual e instala as dependências (Windows PowerShell).
Set-Location (Join-Path $PSScriptRoot "..")
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Write-Host "Instalado. Ative com: .\.venv\Scripts\Activate.ps1"
