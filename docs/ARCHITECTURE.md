# Architecture

## Components

### Master Bot

The master bot is used only by the super user and trusted platform staff.

Responsibilities:

- Manage reseller admins.
- Register seller bot tokens manually.
- Start, stop, disable, and delete seller bot containers.
- Assign Marzban panels or Marzban admins to resellers.
- Manage global base plans and default pricing.
- Manage reseller wallets and debt/credit.
- View global sales and usage reports.
- Configure payment methods and forced channel join rules.
- Send broadcasts to resellers or all buyers.
- Run backups and inspect logs.

### Seller Bot Runtime

One Python runtime is reused for all seller bots. Each seller bot container receives a bot id/token and loads its reseller config from Postgres.

Buyer features:

- Show reseller-specific plans and prices.
- Buy VPN service.
- Card-to-card payment upload and admin approval.
- Wallet charge.
- View services.
- Renew service.
- Increase volume or duration.
- Receive subscription link and QR code.
- Open support tickets.
- Request trial account where allowed.
- View connection guide.

Reseller admin features inside seller bot:

- `/admin` panel.
- Manage own buyers.
- Manual renew/delete/suspend.
- Define reseller-specific plans and discounts.
- Manage discount codes.
- View wallet and transactions.
- Daily/weekly sales reports.
- Broadcast to own buyers.
- Optional node/usage stats.

## Data Ownership

Every scoped row must include `reseller_id`:

- buyers
- seller bots
- orders
- payments
- services
- tickets
- plans where reseller-owned
- discount codes
- broadcasts
- Marzban users

Global rows may omit `reseller_id`:

- platform settings
- global plans
- server inventory
- Marzban panel definitions
- audit logs where target is global

## Provisioning Flow

1. Super user adds reseller in master bot.
2. Super user enters reseller seller-bot token.
3. Master bot stores token encrypted.
4. Master bot assigns panel credentials or Marzban admin scope.
5. Master bot launches one seller container with `SELLER_BOT_ID`.
6. Buyer purchases in seller bot.
7. Seller bot creates order and payment request.
8. Reseller or payment adapter approves payment.
9. Provisioning service creates or updates Marzban user.
10. Seller bot returns subscription link and QR code.

## Deployment Model

Use Docker Compose on the main application server:

- `postgres`
- `master-bot`
- `seller-runtime-image`
- `worker`
- dynamic seller bot containers started by master bot through Docker API

For safer production hardening, replace direct Docker socket access later with a small internal runtime-controller service.

