#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/app/data/sellers}"
DEST="${2:-/app/backups/sellers}"
mkdir -p "$DEST"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
find "$ROOT" -name bot.sqlite3 | while read -r db; do
  seller_id="$(basename "$(dirname "$db")")"
  cp "$db" "$DEST/${seller_id}-${timestamp}.sqlite3"
done
echo "Backup completed to $DEST"
