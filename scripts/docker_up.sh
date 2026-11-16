#!/usr/bin/env bash
# Sobe API + PostgreSQL com Docker Compose e roda os testes dentro do container.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose up --build -d
echo "Aguardando a API ficar saudável..."
for i in $(seq 1 30); do
  if curl -fs http://localhost:8000/health >/dev/null; then
    echo "API no ar: http://localhost:8000/docs"
    exit 0
  fi
  sleep 2
done
echo "A API não respondeu a tempo. Veja os logs com: docker compose logs api" >&2
exit 1
