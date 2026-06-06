#!/usr/bin/env sh
set -eu

APP_DIR="${APP_DIR:-/opt/vpn-bot-platform}"

cd "$APP_DIR"
docker compose run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  master-bot \
  python -m vpn_bot_platform.master_bot.restart_sellers

