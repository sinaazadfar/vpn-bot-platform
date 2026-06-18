# VPN Bot Platform

New Python Telegram bot platform for a VPN reseller business with three access levels:

- Super user: owns the platform and all infrastructure.
- Admin/reseller: sells through a dedicated bot and can manage only their own customers.
- Buyer: buys, renews, upgrades, and receives VPN subscriptions from a reseller bot.

The target architecture uses two bot runtimes:

- `master_bot`: one central bot for the super user.
- `seller_bot`: one reusable runtime that can be launched many times, once per reseller token.

## Source Reuse

Existing folders reviewed:

- `panel_configs`: current two-bot prototype. Reuse its manager/seller separation, Docker seller spawning, encrypted credentials, Postgres recommendation, migrations, and Marzban client ideas.
- `my-servers`: server inventory and Marzban/admin-controller deployment notes. Reuse only non-secret deployment topology and Marzban endpoint patterns.

Do not copy real tokens, SSH keys, passwords, or production `.env` values into this project.

## First Milestone

Build a deployable foundation:

- Fast async Telegram bots using `aiogram`.
- Postgres shared database.
- Docker Compose for master bot, worker services, and seller bot containers.
- Master bot can register resellers and launch seller bot containers.
- Seller bot can show plans and create Marzban users after manual payment approval.
- GitHub Actions deploys to the selected server after push.

See [docs/ROADMAP.md](docs/ROADMAP.md) for the staged work plan.

## Local Verification

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m pytest tests
.\.venv\Scripts\python.exe -m alembic heads
```

Docker image builds require Docker Desktop or a Docker daemon:

```powershell
docker build -f deploy\Dockerfile -t vpn-bot-platform:local .
```

## Production Target

Production deployment target is `server-04`.

SSH alias:

```powershell
ssh server-04
```

Default app path:

```text
/opt/vpn-bot-platform
```

GitHub Actions deployment expects these secrets:

- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- `DEPLOY_APP_DIR`
- `DEPLOY_PORT` (optional, defaults to `22`)

See [docs/DEPLOY_SERVER_04.md](docs/DEPLOY_SERVER_04.md) for first-time setup, manual deploy, rolling seller restarts, and Postgres backups.
