# Deploy To Server-04

Production target:

```bash
ssh server-04
```

App path:

```bash
/opt/vpn-bot-platform
```

## First-Time Setup

Run on `server-04`:

```bash
sudo mkdir -p /opt/vpn-bot-platform
sudo chown "$USER:$USER" /opt/vpn-bot-platform
cd /opt/vpn-bot-platform
git clone <REPO_URL> .
cp .env.example .env
```

Edit `.env` on the server and set production values:

- `DATABASE_URL=postgresql+asyncpg://vpn_platform:<password>@postgres:5432/vpn_platform`
- `POSTGRES_PASSWORD`
- `FERNET_KEY`
- `MASTER_BOT_TOKEN`
- `SUPER_USER_TELEGRAM_ID`
- `CARD_TO_CARD_INSTRUCTIONS`
- Marzban/trial settings as needed

Generate `FERNET_KEY`:

```bash
python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

## Manual Deploy

From your local machine or a self-hosted runner that has `ssh server-04` configured:

```bash
ssh server-04 "APP_DIR=/opt/vpn-bot-platform DEPLOY_BRANCH=main sh /opt/vpn-bot-platform/deploy/deploy.sh"
```

Deploy script actions:

- Fetches and resets to `origin/main`.
- Builds `master-bot`, `worker`, and seller runtime images.
- Runs `alembic upgrade head`.
- Restarts `master-bot` and `worker`.
- Rebuilds the seller runtime image.
- Restarts seller bot containers that were previously in `running` state.
- Runs `deploy/healthcheck.sh`.

## Postgres Backups

Manual backup on `server-04`:

```bash
APP_DIR=/opt/vpn-bot-platform BACKUP_DIR=/opt/vpn-bot-platform/backups/postgres \
  sh /opt/vpn-bot-platform/deploy/backup-postgres.sh
```

Preferred systemd timer:

```bash
APP_DIR=/opt/vpn-bot-platform sh /opt/vpn-bot-platform/deploy/install-backup-timer.sh
```

Optional cron entry if systemd timers are not desired:

```cron
15 3 * * * APP_DIR=/opt/vpn-bot-platform BACKUP_DIR=/opt/vpn-bot-platform/backups/postgres sh /opt/vpn-bot-platform/deploy/backup-postgres.sh
```

Backups are written as gzip SQL dumps and files older than 14 days are removed.

## GitHub Actions

The deploy job runs on a GitHub-hosted Ubuntu runner and SSHes into `server-04`.

Required GitHub secrets:

- `DEPLOY_HOST`: public IP or DNS name for `server-04`
- `DEPLOY_USER`: SSH user allowed to deploy
- `DEPLOY_SSH_KEY`: private SSH key for `DEPLOY_USER`
- `DEPLOY_APP_DIR=/opt/vpn-bot-platform`
- `DEPLOY_PORT`: optional, defaults to `22`

The server itself must have Docker, Docker Compose, Git, and access to the repository origin.

## Bot Update Mode

Production currently uses polling. Webhook mode is deferred until a stable HTTPS domain/subdomain is assigned. See `docs/WEBHOOK_MODE.md`.

## Production Verification

After deploy:

```bash
APP_DIR=/opt/vpn-bot-platform sh /opt/vpn-bot-platform/deploy/healthcheck.sh
cd /opt/vpn-bot-platform && docker compose ps
```
