# Roadmap

## Phase 0 - Inventory And Decisions

- [x] Inspect existing folders.
- [x] Identify reusable source project: `panel_configs`.
- [x] Identify server deployment reference: `my-servers`.
- [x] Create clean platform folder and AI handoff docs.
- [x] Confirm which server will host the master platform. Target: `server-04`.
- [x] Confirm domain/subdomain for bot webhook mode if webhooks are preferred.
- [x] Confirm whether bots should use polling first or webhook first.

Decision: use polling for production MVP on `server-04`. Webhook mode is deferred until a stable HTTPS domain/subdomain is assigned.

## Phase 1 - Foundation

- [x] Create Python package structure under `src/vpn_bot_platform`.
- [x] Add `pyproject.toml`, linting, tests, and dev commands.
- [x] Add Postgres models and Alembic migrations.
- [x] Implement settings loader and secret encryption.
- [x] Port the clean parts of Marzban API client from `panel_configs/app/seller_bot/marzban.py`.
- [x] Add repository/service layer with tenant-safe query helpers.

Deliverable: tests pass locally and schema can migrate on Postgres.

## Phase 2 - Master Bot MVP

- [x] Super user authentication by Telegram ID.
- [x] Add/edit/disable reseller admins. Initial add/list commands exist.
- [x] Register seller bot token manually.
- [x] Store encrypted seller token.
- [x] Assign Marzban panel credentials.
- [x] Start/stop seller bot container.
- [x] Show seller health/log status.

Deliverable: master bot can create and run one seller bot.

## Phase 3 - Seller Bot MVP

- [x] Buyer `/start` and profile creation.
- [x] Plan listing.
- [x] Manual card-to-card payment request.
- [x] Reseller approval screen.
- [x] Marzban user creation.
- [x] Subscription link and QR code response.
- [x] Buyer service list.
- [x] Basic renewal.

Deliverable: real buyer can purchase and receive a VPN subscription.

## Phase 4 - Business Features

- [x] Wallets and reseller balance accounting.
- [x] Discounts and coupon codes.
- [x] Trial accounts with anti-abuse limits.
- [x] Tickets.
- [x] Buyer broadcasts per reseller.
- [x] Global broadcasts from master bot.
- [x] Daily/weekly reports.
- [x] Forced join settings.

Deliverable: platform can support regular reseller operations.

## Phase 5 - CI/CD And Production

- [x] Add GitHub Actions test workflow.
- [x] Build Docker images on push to `main`.
- [x] Deploy to `server-04` through SSH or self-hosted runner.
- [x] Run database migrations during deploy.
- [x] Restart master bot and worker.
- [x] Recreate seller runtime image.
- [x] Rolling restart seller bot containers.
- [x] Add backup job for Postgres.

Deliverable: push to `main` updates production after tests pass.

CI note: Docker build requires a runner with Docker available. Local Docker verification was attempted, but Docker Desktop/daemon was not running on this workstation.

Production target: deploy to `server-04` at `/opt/vpn-bot-platform` using `ssh server-04`. For GitHub-hosted runners, `server-04` must resolve publicly or be replaced by a reachable host; for a self-hosted runner, its SSH config can provide the alias.

## Phase 6 - Hardening

- [x] Audit log for sensitive actions.
- [x] Rate limits for bot actions.
- [x] Runtime-controller service instead of raw Docker socket in master bot.
- [x] Payment gateway adapters.
- [x] Multi-panel routing.
- [x] Monitoring and alerting.
- [x] Disaster recovery runbook.

Hardening notes:

- Audit entries are stored in `audit_logs` for seller runtime changes, payment approvals, wallet approvals, ticket admin actions, broadcasts, plan/discount changes, and panel registration/assignment.
- Bot command rate limits use `rate_limit_buckets` and `BOT_RATE_LIMIT_PER_MINUTE`.
- Master services now depend on a `SellerRuntimeController` interface; Docker remains the current implementation.
- Payment requests use adapter interfaces, with card-to-card as the default adapter.
- Provisioning uses `PanelRouter` with active assignment priority/weight fields.
- Monitoring and disaster recovery docs live in `docs/MONITORING.md` and `docs/DISASTER_RECOVERY.md`.

## Phase 7 - Button-First User Experience

Goal: make both Telegram bots usable through guided menus and buttons, while keeping slash commands as power-user/admin shortcuts.

Telegram UI note: Telegram bots cannot render arbitrary button colors in normal chat messages. The UX should use inline/reply keyboards, consistent emoji/status symbols, message formatting, media/QR assets, and clear navigation to create a polished visual system.

### Shared UI Kit

- [x] Create `src/vpn_bot_platform/common/ui/` package.
- [x] Add shared button builders for inline keyboards.
- [x] Add shared reply keyboard builders for persistent main menus where useful.
- [x] Add callback data builders/parsers with short, Telegram-safe callback strings.
- [x] Add shared message formatters for titles, sections, IDs, prices, dates, and status rows.
- [x] Add common navigation buttons:
  - [x] Home
  - [x] Back
  - [x] Refresh
  - [x] Cancel
  - [x] Confirm
- [x] Add common status labels:
  - [x] Active
  - [x] Suspended
  - [x] Disabled
  - [x] Pending
  - [x] Running
  - [x] Stopped
  - [x] Error
  - [x] Paid
  - [x] Failed
- [x] Add pagination helper for long lists.
- [x] Add confirmation keyboard helper for destructive actions.
- [x] Add tests for keyboard builders and callback parsing.

### Master Bot Main Menu

- [x] Replace `/start` response with a button dashboard.
- [x] Keep `/admin` as an alias for the same dashboard.
- [x] Add top-level master menu buttons:
  - [x] Resellers
  - [x] Seller Bots
  - [x] Panels
  - [x] Plans
  - [x] Discounts
  - [x] Broadcasts
  - [x] Reports
  - [x] Settings
  - [x] System
- [x] Add callback handlers for every top-level menu.
- [x] Add a persistent "Home" action from every submenu.
- [x] Add tests for top-level menu routing.

### Master Bot Reseller UX

- [x] Add reseller list screen with pagination.
- [x] Add reseller detail screen with status, Telegram ID, wallet balance, and seller bot count.
- [x] Add reseller action buttons:
  - [x] Rename
  - [x] Activate
  - [x] Suspend
  - [x] Disable
  - [x] Seller Bots
  - [x] Plans
  - [x] Panel Assignments
- [x] Add guided FSM flow for adding a reseller:
  - [x] Ask Telegram ID.
  - [x] Ask display name.
  - [x] Confirm before create.
  - [x] Show created reseller detail.
- [x] Add guided FSM flow for renaming a reseller:
  - [x] Select reseller by button.
  - [x] Ask new display name.
  - [x] Confirm before update.
  - [x] Show updated reseller action screen.
- [x] Add confirm dialog for suspend/disable.
- [x] Add audit log entries for button-based reseller changes.
- [x] Keep slash commands:
  - [x] `/add_reseller`
  - [x] `/rename_reseller`
  - [x] `/set_reseller_status`
  - [x] `/disable_reseller`
  - [x] `/list_resellers`

### Master Bot Seller Bot UX

- [x] Add seller bot list screen with status labels.
- [x] Add seller bot detail screen:
  - [x] Name
  - [x] Reseller
  - [x] Status
  - [x] Container name
  - [x] Last error
  - [x] Health
- [x] Add seller bot action buttons:
  - [x] Register New Bot
  - [x] Start
  - [x] Stop
  - [x] Restart
  - [x] Health
  - [x] Logs
  - [x] Disable
- [x] Add guided FSM flow for registering seller bot token:
  - [x] Select reseller.
  - [x] Ask bot name.
  - [x] Ask token.
  - [x] Validate token format.
  - [x] Confirm registration.
  - [x] Optionally start immediately.
- [x] Add log viewer with truncated Telegram-safe code block and refresh button.
- [x] Keep slash commands for power users.

### Master Bot Panel UX

- [x] Add panel list screen with active/disabled status.
- [x] Add panel detail screen:
  - [x] Name
  - [x] Base URL
  - [x] Auth type
  - [x] Active status
  - [x] Assignment count
- [x] Add panel action buttons:
  - [x] Add Token Panel
  - [x] Add Password Panel
  - [x] Assign To Reseller
  - [x] Disable Panel
  - [x] Test Connection
- [x] Add guided FSM flow for token panel registration.
- [x] Add guided FSM flow for password panel registration.
- [x] Add guided FSM flow for assignment:
  - [x] Select reseller.
  - [x] Select panel.
  - [x] Ask optional Marzban admin username.
  - [x] Ask priority.
  - [x] Ask weight.
  - [x] Confirm assignment.
- [x] Add priority/weight editing buttons for multi-panel routing.

### Master Bot Plans And Discounts UX

- [x] Add global/reseller plan list screen.
- [x] Add plan detail screen.
- [x] Add guided FSM flow for creating global plan.
- [x] Add guided FSM flow for creating reseller plan.
- [x] Add plan enable/disable buttons.
- [x] Add discount list screen.
- [x] Add discount detail screen.
- [x] Add guided FSM flow for creating discount:
  - [x] Ask code.
  - [x] Ask percent/fixed.
  - [x] Ask amount.
  - [x] Ask max uses.
  - [x] Confirm.
- [x] Add discount enable/disable buttons.

### Master Bot Broadcasts, Reports, Settings, And System UX

- [x] Add broadcast compose FSM:
  - [x] Ask title.
  - [x] Ask message.
  - [x] Preview.
  - [x] Confirm draft creation.
  - [x] Confirm send.
- [x] Add global broadcast history screen.
- [x] Add report menu:
  - [x] Today
  - [x] Last 7 days
  - [x] Last 30 days
  - [x] Custom days
- [x] Add settings menu:
  - [x] Forced join settings
  - [x] Rate limit settings
  - [x] Trial settings
  - [x] Payment instructions
- [x] Add forced join guided flow:
  - [x] Add required chat.
  - [x] List required chats.
  - [x] Remove required chat.
- [x] Add system menu:
  - [x] Healthcheck
  - [x] Deploy version
  - [x] Backup timer status
  - [x] Recent audit logs
  - [x] Recent errors
- [x] Add button action for reading recent audit logs from `audit_logs`.
- [x] Add button action for showing backup timer status on `server-04` where available.

### Seller Bot Buyer Main Menu

- [x] Replace buyer `/start` text with a button dashboard.
- [x] Add buyer top-level buttons:
  - [x] Buy VPN
  - [x] My Services
  - [x] Renew
  - [x] Wallet
  - [x] Trial
  - [x] Support
  - [x] Guides
- [x] Add persistent reply keyboard for buyer shortcuts if it does not clutter admin usage.
- [x] Add forced-join blocked screen with required chat buttons.
- [x] Add tests for buyer dashboard keyboard.

### Seller Bot Buyer Purchase UX

- [x] Add plan list screen with one card/message per plan or compact paginated list.
- [x] Add `Buy` button for each plan.
- [x] Add coupon step:
  - [x] Enter coupon.
  - [x] Skip coupon.
  - [x] Validate coupon.
  - [x] Show discounted amount.
- [x] Add payment instruction screen:
  - [x] Order ID
  - [x] Payment ID
  - [x] Amount
  - [x] Instructions
  - [x] Support/contact button
- [x] Add order status button.
- [x] Add receipt-upload placeholder flow for future automated proof review.
- [x] Keep `/buy <plan_id> [coupon]` as shortcut.

### Seller Bot Services And Renewal UX

- [x] Add service list screen with active/inactive labels.
- [x] Add service detail screen:
  - [x] Username
  - [x] Traffic limit
  - [x] Expiry
  - [x] Status
  - [x] Subscription link
- [x] Add service action buttons:
  - [x] Get Subscription
  - [x] QR Code
  - [x] Renew
  - [x] Connection Guide
- [x] Add guided renewal flow:
  - [x] Select service.
  - [x] Select plan.
  - [x] Optional coupon.
  - [x] Confirm payment request.
- [x] Keep `/my_services` and `/renew` as shortcuts.

### Seller Bot Wallet UX

- [x] Add wallet dashboard:
  - [x] Balance
  - [x] Recent transactions
  - [x] Charge wallet
- [x] Add guided wallet charge flow:
  - [x] Ask amount.
  - [x] Confirm request.
  - [x] Show card-to-card instructions.
- [x] Add transaction detail screen.
- [x] Keep `/wallet` and `/charge_wallet` as shortcuts.

### Seller Bot Trial UX

- [x] Add trial screen showing availability and limits.
- [x] Add request trial button.
- [x] Add trial result screen with subscription and QR actions.
- [x] Add clear already-used state.
- [x] Keep `/trial` as shortcut.

### Seller Bot Support UX

- [x] Add support dashboard:
  - [x] Open Ticket
  - [x] My Tickets
  - [x] Connection Guides
- [x] Add ticket creation FSM:
  - [x] Ask subject.
  - [x] Ask message.
  - [x] Confirm open.
- [x] Add ticket list screen.
- [x] Add ticket detail screen with recent messages.
- [x] Add reply button and FSM.
- [x] Keep `/ticket`, `/my_tickets`, and `/reply_ticket` as shortcuts.

### Seller Bot Reseller Admin UX

- [x] Replace `/admin` response with admin dashboard buttons.
- [x] Add admin top-level buttons:
  - [x] Pending Payments
  - [x] Provision Orders
  - [x] Wallet Charges
  - [x] Tickets
  - [x] Broadcast
  - [x] Sales Report
  - [x] Customers
  - [x] Plans
- [x] Add pending payment list screen.
- [x] Add payment detail screen with approve/reject buttons.
- [x] Add provision order screen with confirm button.
- [x] Add wallet charge list and approve button.
- [x] Add ticket admin list/detail/reply/close buttons.
- [x] Add reseller broadcast compose FSM with preview/confirm.
- [x] Add sales report preset buttons:
  - [x] Today
  - [x] 7 days
  - [x] 30 days
  - [x] Custom
- [x] Keep seller admin slash commands as shortcuts.

### FSM And Navigation Architecture

- [x] Add FSM state groups for master reseller flows.
- [x] Add FSM state groups for master seller bot flows.
- [x] Add FSM state groups for master panel flows.
- [x] Add FSM state groups for master plan/discount/broadcast/settings flows.
- [x] Add FSM state groups for seller purchase/renew/wallet/ticket flows.
- [x] Add central cancel handler.
- [x] Add stale-state recovery: Home/Cancel should clear state.
- [x] Add permission checks to every callback handler.
- [x] Add callback data size tests.
- [x] Add tests for critical FSM transitions.

### Visual Polish Rules

- [x] Use concise titles and sections instead of long paragraphs.
- [x] Keep IDs visible but compact.
- [x] Use consistent status icons and labels.
- [x] Use confirmation screens for destructive actions.
- [x] Use message edits for menu navigation where possible to reduce chat spam.
- [x] Use new messages for important receipts, QR codes, and final confirmations.
- [x] Truncate logs and long broadcasts safely.
- [x] Avoid exposing secrets in any UI screen or log output.

### Phase 7 Deliverables

- [x] Master bot can be operated mostly through buttons.
- [x] Seller buyer flows can be operated mostly through buttons.
- [x] Seller admin flows can be operated mostly through buttons.
- [x] Existing slash commands still work.
- [x] Tests cover keyboard builders, callback parsing, permission checks, and critical FSM flows.
- [x] Production deploy verifies the new button UX starts without polling/runtime errors.

## Phase 8 - Approved Product Flow Completion

Source of truth: `docs/PRODUCT_FLOW.md`.

Goal: turn the approved combined flow into complete production behavior, using the best storefront flow from ZanborPanel/BotMirzaPanel, the cleaner Python structure from Marzbot-free, and the management/health concepts from Marzban.

### Buyer Storefront

- [ ] Add buyer-facing location/panel choice before plan selection when multiple active routed panels are available.
- [x] Add explicit plan purpose/type support:
  - [x] Purchase plan.
  - [x] Trial plan.
  - [x] Renewal plan.
  - [x] Extra-volume plan.
- [ ] Add direct order payment path in addition to wallet-first payment.
- [ ] Add receipt upload handling for direct order payments.
- [ ] Auto-provision direct order after reseller approval.
- [ ] Add service-specific support shortcut from service detail.
- [ ] Add buyer account screen with wallet, service counts, and recent activity.

### Renewal And Extra Volume

- [x] Split renewal and extra-volume plan selection.
- [x] Implement extra-volume purchase flow.
- [x] Apply extra volume to Marzban data limit.
- [ ] Improve renewal to preserve remaining time where panel behavior allows it.
- [x] Add payment/audit records for renewal and extra-volume changes.

### Seller Admin Operations

- [ ] Add customer search by Telegram ID, username, or service username.
- [ ] Add customer detail screen:
  - [ ] Wallet balance.
  - [ ] Service count.
  - [ ] Orders.
  - [ ] Tickets.
- [ ] Add reseller manual wallet adjustment with confirmation and audit log.
- [ ] Add reseller send-message-to-customer action.
- [ ] Add buyer block/unblock action scoped to reseller.
- [ ] Add seller admin service management:
  - [ ] View service detail.
  - [ ] Disable service.
  - [ ] Revoke subscription.
  - [ ] Reset usage where Marzban supports it.

### Master Platform Controls

- [ ] Add payment settings editor in Master Bot.
- [ ] Add trial settings editor in Master Bot.
- [ ] Add rate limit settings editor in Master Bot.
- [ ] Add plan purpose/type editor in Master Bot.
  - [x] Add command-level purpose support for purchase, trial, renewal, and extra-volume plans.
- [ ] Add reseller-specific discount management.
- [ ] Add reseller-specific payment instruction management.
- [ ] Add richer system health screen with live database, worker, seller runtime, and panel checks.

### Marzban Management

- [ ] Add panel node/system stats screen.
- [ ] Add panel host/inbound summary screen.
- [ ] Add panel-level provisioning error history.
- [ ] Add panel route preview for a reseller before saving routing changes.
- [ ] Add optional dedicated trial panel route.

### UX Polish

- [ ] Use a single Persian-first text style for buyer and reseller screens.
- [ ] Add compact receipt messages for every successful purchase, renewal, wallet charge, and extra-volume action.
- [ ] Add clearer empty states for no plans, no services, no tickets, and no payments.
- [ ] Add safer retry screens for failed Marzban provisioning.
- [ ] Add stronger Telegram-safe truncation for all admin broadcast and log screens.

### Tests And Deploy

- [ ] Add tests for buyer location selection.
- [ ] Add tests for direct order approval provisioning.
- [x] Add tests for extra-volume Marzban update.
- [ ] Add tests for customer search and admin wallet adjustment.
- [ ] Add tests for master callback permission coverage.
- [ ] Deploy Phase 8 increments to `server-04` after each stable slice.
