# Sobe a API localmente com SQLite (Windows PowerShell). Swagger em http://localhost:8000/docs
Set-Location (Join-Path $PSScriptRoot "..")
if (Test-Path .venv) { .\.venv\Scripts\Activate.ps1 }
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
