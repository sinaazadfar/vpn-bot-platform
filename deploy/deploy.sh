#!/usr/bin/env sh
set -eu

APP_DIR="${APP_DIR:-/opt/vpn-bot-platform}"

cd "$APP_DIR"
git fetch --all --prune
git reset --hard "origin/${DEPLOY_BRANCH:-main}"
docker compose --profile migrate build migrate master-bot worker seller-bot
docker compose --profile migrate up --force-recreate --abort-on-container-exit migrate
docker compose up -d master-bot worker
docker compose build seller-bot
APP_DIR="$APP_DIR" sh "$APP_DIR/deploy/restart-sellers.sh"
APP_DIR="$APP_DIR" sh "$APP_DIR/deploy/healthcheck.sh"
