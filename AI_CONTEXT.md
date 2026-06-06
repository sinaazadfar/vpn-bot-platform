# AI Context

This file is the primary handoff for AI agents working on this project.

## Product Goal

Create a production-ready Python Telegram bot platform for selling VPN accounts through Marzban panels.

The platform has three roles:

- `super_user`: full owner, manages servers, panels, resellers, plans, payments, global settings, broadcasts, backups, and logs.
- `reseller_admin`: owns one or more seller bots, manages only their plans, buyers, wallet, discounts, tickets, and sales reports.
- `buyer`: uses a reseller bot to buy, renew, upgrade, view subscription links, get QR codes, submit tickets, and request trials.

## Runtime Shape

Use exactly two bot applications:

- `master_bot`: central owner bot. It provisions resellers and launches seller bots.
- `seller_bot`: reusable seller runtime. Each running instance is configured by `SELLER_BOT_ID` or token and loads its reseller scope from the database.

## Existing Project Signals

Important existing code:

- `../panel_configs/app/manager_bot`: current manager bot with Docker seller container management.
- `../panel_configs/app/seller_bot`: current seller bot runtime and Marzban integration.
- `../panel_configs/app/common`: config, encryption, database, models, repos, i18n.
- `../panel_configs/docker-compose.yml`: Postgres + manager + seller compose pattern.
- `../my-servers/ADMIN_CONTROLLER.md`: Marzban admin-controller server-02 deployment reference.

Use these as references, not as a blind copy.

## Design Rules

- Keep tenant boundaries strict. Every buyer, order, ticket, plan, and Marzban user must belong to one reseller.
- Master bot can see all data. Reseller bot can see only its own data.
- Store Telegram tokens and Marzban credentials encrypted.
- Prefer Postgres for all shared deployment environments.
- Seller bots should be disposable containers. The database is the source of truth.
- CI/CD should build images, run tests, and deploy through SSH or a self-hosted runner.

## Suggested Python Stack

- Python 3.12+
- `aiogram` for Telegram bots
- `SQLAlchemy` async ORM
- `asyncpg` for Postgres
- `alembic` for migrations
- `httpx` for Marzban API calls
- `pydantic-settings` for env config
- `cryptography` Fernet for encrypted secrets
- `qrcode` / `Pillow` for QR output
- `pytest` / `pytest-asyncio` for tests

## Initial Module Layout

```text
src/
  vpn_bot_platform/
    common/
      config.py
      crypto.py
      db.py
      models.py
      repositories.py
      security.py
    integrations/
      marzban.py
      telegram.py
      payments.py
      docker_runtime.py
    master_bot/
      main.py
      handlers/
      services/
    seller_bot/
      main.py
      handlers/
      services/
    workers/
      billing.py
      provisioning.py
```

## Non-Goals For The First Build

- Automatic BotFather token creation. Telegram does not provide a normal public HTTP API for creating bots through BotFather. Start with manual token entry; document optional future automation separately.
- Full payment gateway integration. Start with card-to-card/manual approval, then add gateway adapters.
- Multi-panel load balancing. Start with assigning one Marzban panel to a reseller; design the schema so multiple panels can be added later.

