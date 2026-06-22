# External Seller Bot Reference

Selected reference bot: `govfvck/Marzbot-free`

Location in this repo:

```text
external/seller-bots/marzbot-free
```

Why this one:

- It is Python-based and uses aiogram, so it is closest to our current bot stack.
- It has a stronger user storefront flow than the PHP alternatives:
  - account dashboard
  - wallet charge
  - purchase flow
  - subscription list
  - proxy/service detail
  - renewal-oriented service management
- It is structurally easier to study or run beside our platform than BotMirzaPanel or ZanborPanel, which are PHP projects with different database/runtime assumptions.

Important license note:

- `Marzbot-free` is AGPL-3.0.
- Keep it as an external submodule unless we intentionally decide to adopt AGPL obligations for copied/derived code.
- For now, use it as the cloned seller-bot reference and implementation candidate, while keeping our current seller bot intact.

Current decision:

- Our existing seller bot remains the production seller bot.
- `Marzbot-free` is cloned into the project for comparison, testing, and possible future replacement work.
- Do not copy large source blocks from it into our codebase without an explicit license decision.

Master bot support:

- External seller bots can now be registered as templates from the master bot.
- Supported commands:
  - `/add_external_template <key> <name> <repo_url> <ref> [local_path] [license] [runtime_adapter]`
  - `/list_external_templates`
  - `/sync_external_template <template_id_or_key>`
  - `/add_external_seller_bot <reseller_telegram_id> <bot_name> <bot_token> <template_id_or_key>`
- The master bot also exposes `External Bots` buttons for listing and syncing templates.
- External seller bot records use `runtime_type=external_template`.

Simple Seller note:

- Simple Seller is not registered as an external template for production.
- Use `Add Seller Bot` > `Simple Seller` in the master bot. It creates a native platform seller bot with `ui_profile=simple_seller`, so it uses the shared Postgres database.

Runtime boundary:

- External bot templates are registry records today.
- The native seller-bot container runner intentionally refuses to start `external_template` bots.
- Running external templates requires a runtime adapter/controller that understands that external bot's env files, database, Docker image, migrations, and update process.
