# Data Model Draft

Core tables:

- `users`: Telegram users known to the platform.
- `resellers`: reseller/admin profile and status.
- `seller_bots`: one row per reseller bot token/runtime.
- `marzban_panels`: encrypted panel credentials and API URL.
- `reseller_panel_assignments`: reseller-to-panel scope.
- `plans`: global and reseller-specific plans.
- `orders`: buyer purchase/renew/upgrade requests.
- `payments`: payment proof, gateway status, approval state.
- `wallet_transactions`: buyer and reseller wallet ledger.
- `vpn_services`: provisioned Marzban user records and subscription metadata.
- `tickets`: buyer support tickets.
- `ticket_messages`: ticket thread messages.
- `discount_codes`: reseller or global discounts.
- `broadcasts`: outgoing broadcast jobs.
- `audit_logs`: sensitive action history.

Critical constraints:

- Scoped business rows need `reseller_id`.
- `seller_bots.token_encrypted` must never expose plaintext in logs.
- Use database transactions for payment approval and provisioning state changes.
- Keep ledger-style wallet transactions append-only.

