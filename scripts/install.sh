#!/usr/bin/env bash
# Cria um ambiente virtual e instala as dependências (Linux/macOS/WSL).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "Instalado. Ative com: source .venv/bin/activate"
