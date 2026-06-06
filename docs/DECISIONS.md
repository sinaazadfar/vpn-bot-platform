# Decisions

## 001 - Two Bot Types

Use one `master_bot` plus many `seller_bot` instances.

Reason:

- Matches the required three access levels.
- Keeps buyer traffic away from the super-user bot.
- Lets each reseller have their own Telegram bot token and brand.
- Allows the seller runtime to be updated once and redeployed for every reseller.

## 002 - Manual Bot Token Entry First

Start with manual token entry from BotFather.

Reason:

- Telegram does not provide a normal public API for creating bots through BotFather.
- Automating BotFather chat control is fragile and can violate platform expectations.
- Manual token entry is enough for the MVP; the master bot can still create and run the seller container automatically after the token is saved.

## 003 - Postgres As Source Of Truth

Use Postgres for shared environments.

Reason:

- Master bot, seller bot instances, and workers must share data.
- SQLite is not reliable across multiple containers.
- Existing `panel_configs` already points to Postgres as the recommended Docker deployment mode.

## 004 - Polling First

Use Telegram polling for the MVP unless webhook infrastructure is confirmed.

Reason:

- Polling is simpler to launch across multiple seller bot containers.
- Webhooks can be added later when domains, TLS, reverse proxy, and routing are finalized.

