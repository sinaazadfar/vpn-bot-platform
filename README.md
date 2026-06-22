# VPN Seller Bot

Python Telegram seller bot for VPN subscriptions backed by Marzban.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env`, then run:

```powershell
python -m bot
```

## Tests

```powershell
pytest
```

## Master Bot

The master bot from `vpn-bot-platform` is included under `src/vpn_bot_platform`.

```powershell
pip install -e ".[dev]"
python -m vpn_bot_platform.master_bot.main
```

For the platform database, set `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`,
`DATABASE_URL`, `FERNET_KEY`, `MASTER_BOT_TOKEN`, and `SUPER_USER_TELEGRAM_ID` in
`.env`. For local Docker Compose, start Postgres and run migrations with:

```powershell
docker compose up -d postgres
alembic upgrade head
```

Create a seller bot, reseller/admin record, and Marzban panel from the master bot:

```text
/create_seller_bot <admin_telegram_id> <seller_bot_name> <seller_bot_token> <panel_name> <panel_base_url> <marzban_username> <marzban_password> [marzban_admin_username] [volume_limit_gb]
```

Docker/CI deploy assets are in `deploy/`, `docker-compose.yml`, and
`.github/workflows/ci-cd.yml`.
