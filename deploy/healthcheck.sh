#!/usr/bin/env sh
set -eu

APP_DIR="${APP_DIR:-/opt/vpn-bot-platform}"
cd "$APP_DIR"

docker compose ps --status running postgres master-bot worker >/dev/null
docker compose exec -T postgres pg_isready \
  -U "${POSTGRES_USER:-vpn_platform}" \
  -d "${POSTGRES_DB:-vpn_platform}" >/dev/null

if ! docker compose logs --since 2m master-bot | grep -q "polling started"; then
  docker compose ps master-bot | grep -q "Up"
fi

echo "vpn-bot-platform healthcheck ok"
