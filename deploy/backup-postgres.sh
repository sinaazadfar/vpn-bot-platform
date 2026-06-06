#!/usr/bin/env sh
set -eu

APP_DIR="${APP_DIR:-/opt/vpn-bot-platform}"
BACKUP_DIR="${BACKUP_DIR:-/opt/vpn-bot-platform/backups/postgres}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

cd "$APP_DIR"
mkdir -p "$BACKUP_DIR"
docker compose exec -T postgres pg_dump \
  -U "${POSTGRES_USER:-vpn_platform}" \
  "${POSTGRES_DB:-vpn_platform}" \
  | gzip > "$BACKUP_DIR/postgres-$TIMESTAMP.sql.gz"

find "$BACKUP_DIR" -type f -name 'postgres-*.sql.gz' -mtime +14 -delete

