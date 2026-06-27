# Product Flow

This document is the approved product flow for the VPN bot platform. It combines the strongest flows from ZanborPanel, BotMirzaPanel, Marzbot-free, and the official Marzban Telegram bot pattern while keeping this platform's two-bot architecture.

## Product Shape

The platform has three roles:

- Super User: operates the Master Bot and owns platform-wide settings.
- Reseller/Admin: owns one or more Seller Bots and manages their own buyers.
- Buyer: uses only the Seller Bot of the reseller they buy from.

The platform has two Telegram bot types:

- Master Bot: central control plane for resellers, seller bots, panels, plans, discounts, reporting, settings, and system health.
- Seller Bot: reseller-owned storefront for buyers and reseller admin operations.

## Master Bot Flow

Main menu (daily-first):

- Seller Bots (list and manage)
- Add Seller Bot (unified onboarding wizard — primary CTA)
- Reports
- Platform Settings (advanced: resellers, panels, plans, discounts, broadcasts, system)

Reply keyboard shortcuts mirror the inline menu in Persian.

### Unified Seller Bot Onboarding

One wizard creates a new owner, Marzban panel, and seller bot in a single transaction:

1. Super User opens **Add Seller Bot**.
2. Selects bot type: **Platform** or **Simple Seller**.
3. Enters new owner Telegram numeric ID and display name.
4. Enters bot display name and BotFather token.
5. Enters new panel name, base URL, and auth mode (token or username/password).
6. Optionally sets Marzban admin username scope.
7. Sets initial volume stock (GB).
8. Confirms summary (secrets hidden).
9. Master Bot provisions reseller + panel + bot + panel assignment atomically.
10. On success: optional auto-start, panel connection test, and actions **Start bot**, **Open bot config**, **Test panel**.

Super User (`SUPER_USER_TELEGRAM_ID`) is co-admin on every provisioned bot.

Separate **Add Reseller** and **Add Panel** flows are demoted under Platform Settings for advanced edge cases only (for example multi-panel routing). Use **Assign Panel** when an existing panel must be linked to another reseller.

### Reseller Flow

1. Super User opens Platform Settings → Resellers.
2. Browses existing owners (created automatically by Add Seller Bot).
3. Opens reseller detail for rename, activate, suspend, disable, seller bots, plans, and panel assignments.

### Seller Bot Management

1. Super User opens Seller Bots.
2. List rows show status, used/limit GB, and health badge when available.
3. Opens bot config card for runtime and observability actions:
   - Start | Stop | Restart
   - Health | Logs
   - Volume stock, pricing, admins, panel link
4. Production runtime starts the Seller Bot container when requested.

### Panel Flow (Advanced)

1. Super User opens Platform Settings → Panels.
2. Lists registered panels; tests connection; changes token or password; disables panels.
3. **Assign Panel** links an existing panel to a reseller with priority, weight, and optional Marzban admin username.
4. For new onboarding, use **Add Seller Bot** instead of adding panels separately.

### Plan Flow

1. Super User opens Plans.
2. Creates a global plan or reseller-specific plan.
3. Defines:
   - name
   - price
   - duration
   - data limit
   - plan purpose: purchase, trial, renewal, or extra volume
4. Enables or disables the plan.
5. Active plans become visible in Seller Bots according to scope.

### Discount Flow

1. Super User opens Discounts.
2. Creates a global or reseller-specific discount.
3. Defines code, type, amount, and max uses.
4. Enables or disables the discount.
5. Buyer purchase and renewal flows can validate the code before payment.

### Master Reporting Flow

The Reports menu shows:

- today
- last 7 days
- last 30 days
- custom days
- reseller count
- buyer count
- completed order count and value
- new service count

The System menu shows:

- health
- deployed version
- backup status guidance
- recent audit logs
- recent runtime errors guidance

## Seller Bot Buyer Flow

Buyer main menu:

- Buy VPN
- My Services
- Renew
- Extra Volume
- Wallet
- Trial
- Support
- Guides
- My Account

### Start Flow

1. Buyer sends `/start`.
2. Seller Bot creates or updates buyer profile.
3. Seller Bot checks if buyer is blocked.
4. Seller Bot checks forced join.
5. If required chats are missing:
   - shows required chat list.
   - shows Check Again button.
6. If allowed:
   - shows buyer dashboard.

### Buy VPN Flow

1. Buyer selects Buy VPN.
2. Seller Bot shows location/panel choices if more than one buyer-facing location exists.
3. Buyer selects a plan.
4. Seller Bot shows plan detail:
   - name
   - duration
   - traffic
   - price
   - wallet balance
5. Buyer can:
   - buy with wallet
   - enter coupon
   - skip coupon
   - charge wallet
   - go back
6. Seller Bot validates coupon and shows final amount.
7. Buyer confirms.
8. If wallet balance is enough:
   - Seller Bot creates the Marzban user.
   - stores order, payment, and VPN service.
   - sends subscription link.
   - sends QR code.
   - shows connection guide shortcut.
9. If wallet balance is not enough:
   - Seller Bot creates a payment request.
   - buyer follows payment flow.
   - service is provisioned after approval.

### Payment Flow

The preferred MVP model is wallet-first:

1. Buyer opens Wallet.
2. Selects Charge Wallet.
3. Enters or selects amount.
4. Seller Bot creates a wallet charge request.
5. Buyer receives card-to-card instructions or gateway payment link.
6. Buyer uploads receipt for manual card-to-card.
7. Reseller admin approves or rejects.
8. Approved payments increase buyer wallet.
9. Buyer purchases service from wallet balance.

Direct order payment remains supported as a later enhancement:

1. Buyer chooses plan.
2. Seller Bot creates order invoice.
3. Buyer pays directly.
4. Approval provisions the selected service automatically.

### My Services Flow

1. Buyer opens My Services.
2. Seller Bot lists services with compact status labels:
   - active
   - expired
   - exhausted
   - disabled
3. Buyer selects a service.
4. Seller Bot shows:
   - Marzban username
   - status
   - used traffic
   - total traffic
   - expiry
   - subscription link
5. Buyer actions:
   - Get Subscription
   - QR Code
   - Renew
   - Extra Volume
   - Connection Guide
   - Support for this service

### Renewal Flow

1. Buyer selects service.
2. Buyer selects renewal plan.
3. Optional coupon step.
4. Seller Bot shows final amount.
5. Buyer confirms.
6. Wallet payment is applied.
7. Seller Bot updates Marzban expiry.
8. Seller Bot records transaction and confirms renewal.

### Extra Volume Flow

1. Buyer selects service.
2. Buyer selects extra-volume plan.
3. Optional coupon step.
4. Seller Bot shows final amount.
5. Buyer confirms.
6. Wallet payment is applied.
7. Seller Bot increases Marzban data limit.
8. Seller Bot records transaction and confirms volume increase.

### Trial Flow

1. Buyer opens Trial.
2. Seller Bot checks:
   - previous trial grants.
   - reseller trial limits.
   - forced join.
3. If allowed:
   - creates trial service on the configured panel route.
   - sends subscription link and QR.
4. If not allowed:
   - shows the exact reason.

### Support Flow

1. Buyer opens Support.
2. Buyer can:
   - open ticket.
   - view tickets.
   - open connection guides.
3. New ticket asks subject and message.
4. Buyer confirms.
5. Reseller admin receives and replies from Seller Bot admin menu.
6. Buyer receives notifications and can reply.

## Seller Bot Reseller Admin Flow

Admin menu:

- Pending Payments
- Provision Orders
- Wallet Charges
- Tickets
- Customers
- Services
- Plans
- Discounts
- Broadcast
- Sales Report
- Settings

### Pending Payment Flow

1. Reseller opens Pending Payments.
2. Selects payment.
3. Sees buyer, amount, order, method, and receipt status.
4. Approves or rejects.
5. Approved wallet charges increase balance.
6. Approved direct order payments trigger provisioning.
7. Rejected payments notify buyer.

### Customer Flow

1. Reseller opens Customers.
2. Searches or selects buyer.
3. Sees:
   - wallet balance
   - service count
   - orders
   - tickets
4. Actions:
   - manual wallet adjustment
   - send message
   - view services
   - block or unblock

### Report Flow

Reports include:

- today
- last 7 days
- last 30 days
- custom days
- completed orders
- approved payments
- wallet charges
- new buyers
- new services

## Implementation Principles

- All common flows should be button-first.
- Slash commands stay as shortcuts for power users.
- Buyer-facing flows should be short, linear, and recoverable with Back/Home.
- Destructive admin actions need confirmation.
- Secrets must never be shown in Telegram messages.
- Important receipts, QR codes, and final confirmations should be new messages.
- Menu navigation should prefer message edits to reduce chat noise.
- Marzban provisioning should stay in service-layer code, not handlers.
- Multi-panel routing should stay centralized in the routing service.

## Source Inspirations

- ZanborPanel: strongest buyer storefront flow in Persian.
- BotMirzaPanel: broadest shop/admin feature set.
- Marzbot-free: clean Python/aiogram architecture and service separation.
- Official Marzban Telegram bot: management and health/notification concepts.

## Simple Seller Implementation Notes (2026)

- Global `BlockCheckMiddleware` and `ForcedJoinMiddleware` in `bot/app.py`
- Admin users: filters, search pagination, profile sync, wallet ledger
- Admin payments: paginated pending list with receipt view
- HTML wallet/payment notifications in `bot/notifications.py`
- Buyer: wallet ledger, trial, tickets, renew vs volume split, support fix
- Master Bot: panel password/token change from seller bot panel menu
- Backup script: `scripts/backup_seller_sqlite.sh`
