# Disaster Recovery Runbook

## Backup

Backups are created by `deploy/backup-postgres.sh` into:

```text
/opt/vpn-bot-platform/backups/postgres
```

Run a manual backup:

```sh
APP_DIR=/opt/vpn-bot-platform sh /opt/vpn-bot-platform/deploy/backup-postgres.sh
```

## Restore Postgres

1. Stop bots:

```sh
cd /opt/vpn-bot-platform
docker compose stop master-bot worker
```

2. Restore a backup:

```sh
gzip -dc backups/postgres/postgres-YYYYMMDDTHHMMSSZ.sql.gz \
  | docker compose exec -T postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB"
```

3. Run migrations:

```sh
docker compose --profile migrate up --force-recreate --abort-on-container-exit migrate
```

4. Start services:

```sh
docker compose up -d master-bot worker
APP_DIR=/opt/vpn-bot-platform sh deploy/restart-sellers.sh
```

5. Verify:

```sh
APP_DIR=/opt/vpn-bot-platform sh deploy/healthcheck.sh
```

## Full Server Replacement

1. Install Docker and Docker Compose v2.
2. Clone `https://github.com/sinaazadfar/vpn-bot-platform` to `/opt/vpn-bot-platform`.
3. Copy the production `.env` from a secure backup.
4. Restore Postgres from the latest backup.
5. Run the deploy script:

```sh
APP_DIR=/opt/vpn-bot-platform DEPLOY_BRANCH=main sh /opt/vpn-bot-platform/deploy/deploy.sh
```

## Secrets

Do not rotate `FERNET_KEY` without first re-encrypting stored seller bot and Marzban secrets.
