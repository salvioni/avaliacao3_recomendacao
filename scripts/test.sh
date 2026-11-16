#!/usr/bin/env bash
# Roda os testes unitários e de integração.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] && source .venv/bin/activate
python -m pytest -v "$@"
