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

- [ ] Add reseller list screen with pagination.
- [ ] Add reseller detail screen with status, Telegram ID, wallet balance, and seller bot count.
- [x] Add reseller action buttons:
  - [x] Rename
  - [x] Activate
  - [x] Suspend
  - [x] Disable
  - [ ] Seller Bots
  - [ ] Plans
  - [ ] Panel Assignments
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
- [ ] Keep slash commands:
  - [ ] `/add_reseller`
  - [ ] `/rename_reseller`
  - [ ] `/set_reseller_status`
  - [ ] `/disable_reseller`
  - [ ] `/list_resellers`

### Master Bot Seller Bot UX

- [x] Add seller bot list screen with status labels.
- [ ] Add seller bot detail screen:
  - [ ] Name
  - [ ] Reseller
  - [ ] Status
  - [ ] Container name
  - [ ] Last error
  - [ ] Health
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
  - [ ] Optionally start immediately.
- [ ] Add log viewer with truncated Telegram-safe code block and refresh button.
- [ ] Keep slash commands for power users.

### Master Bot Panel UX

- [ ] Add panel list screen with active/disabled status.
- [ ] Add panel detail screen:
  - [ ] Name
  - [ ] Base URL
  - [ ] Auth type
  - [ ] Active status
  - [ ] Assignment count
- [ ] Add panel action buttons:
  - [ ] Add Token Panel
  - [ ] Add Password Panel
  - [ ] Assign To Reseller
  - [ ] Disable Panel
  - [ ] Test Connection
- [ ] Add guided FSM flow for token panel registration.
- [ ] Add guided FSM flow for password panel registration.
- [ ] Add guided FSM flow for assignment:
  - [ ] Select reseller.
  - [ ] Select panel.
  - [ ] Ask optional Marzban admin username.
  - [ ] Ask priority.
  - [ ] Ask weight.
  - [ ] Confirm assignment.
- [ ] Add priority/weight editing buttons for multi-panel routing.

### Master Bot Plans And Discounts UX

- [ ] Add global/reseller plan list screen.
- [ ] Add plan detail screen.
- [ ] Add guided FSM flow for creating global plan.
- [ ] Add guided FSM flow for creating reseller plan.
- [ ] Add plan enable/disable buttons.
- [ ] Add discount list screen.
- [ ] Add discount detail screen.
- [ ] Add guided FSM flow for creating discount:
  - [ ] Ask code.
  - [ ] Ask percent/fixed.
  - [ ] Ask amount.
  - [ ] Ask max uses.
  - [ ] Confirm.
- [ ] Add discount enable/disable buttons.

### Master Bot Broadcasts, Reports, Settings, And System UX

- [ ] Add broadcast compose FSM:
  - [x] Ask title.
  - [x] Ask message.
  - [x] Preview.
  - [x] Confirm draft creation.
  - [ ] Confirm send.
- [ ] Add global broadcast history screen.
- [ ] Add report menu:
  - [x] Today
  - [x] Last 7 days
  - [x] Last 30 days
  - [ ] Custom days
- [ ] Add settings menu:
  - [ ] Forced join settings
  - [ ] Rate limit settings
  - [ ] Trial settings
  - [ ] Payment instructions
- [ ] Add forced join guided flow:
  - [ ] Add required chat.
  - [ ] List required chats.
  - [ ] Remove required chat.
- [ ] Add system menu:
  - [ ] Healthcheck
  - [ ] Deploy version
  - [ ] Backup timer status
  - [ ] Recent audit logs
  - [ ] Recent errors
- [ ] Add button action for reading recent audit logs from `audit_logs`.
- [ ] Add button action for showing backup timer status on `server-04` where available.

### Seller Bot Buyer Main Menu

- [x] Replace buyer `/start` text with a button dashboard.
- [x] Add buyer top-level buttons:
  - [x] Buy VPN
  - [x] My Services
  - [ ] Renew
  - [x] Wallet
  - [x] Trial
  - [x] Support
  - [x] Guides
- [ ] Add persistent reply keyboard for buyer shortcuts if it does not clutter admin usage.
- [ ] Add forced-join blocked screen with required chat buttons.
- [x] Add tests for buyer dashboard keyboard.

### Seller Bot Buyer Purchase UX

- [x] Add plan list screen with one card/message per plan or compact paginated list.
- [x] Add `Buy` button for each plan.
- [ ] Add coupon step:
  - [ ] Enter coupon.
  - [ ] Skip coupon.
  - [ ] Validate coupon.
  - [ ] Show discounted amount.
- [ ] Add payment instruction screen:
  - [ ] Order ID
  - [ ] Payment ID
  - [ ] Amount
  - [ ] Instructions
  - [ ] Support/contact button
- [ ] Add order status button.
- [ ] Add receipt-upload placeholder flow for future automated proof review.
- [ ] Keep `/buy <plan_id> [coupon]` as shortcut.

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
  - [ ] Renew
  - [x] Connection Guide
- [ ] Add guided renewal flow:
  - [ ] Select service.
  - [ ] Select plan.
  - [ ] Optional coupon.
  - [ ] Confirm payment request.
- [ ] Keep `/my_services` and `/renew` as shortcuts.

### Seller Bot Wallet UX

- [x] Add wallet dashboard:
  - [x] Balance
  - [x] Recent transactions
  - [x] Charge wallet
- [x] Add guided wallet charge flow:
  - [x] Ask amount.
  - [x] Confirm request.
  - [x] Show card-to-card instructions.
- [ ] Add transaction detail screen.
- [ ] Keep `/wallet` and `/charge_wallet` as shortcuts.

### Seller Bot Trial UX

- [x] Add trial screen showing availability and limits.
- [x] Add request trial button.
- [x] Add trial result screen with subscription and QR actions.
- [x] Add clear already-used state.
- [ ] Keep `/trial` as shortcut.

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
- [ ] Add ticket detail screen with recent messages.
- [ ] Add reply button and FSM.
- [ ] Keep `/ticket`, `/my_tickets`, and `/reply_ticket` as shortcuts.

### Seller Bot Reseller Admin UX

- [x] Replace `/admin` response with admin dashboard buttons.
- [x] Add admin top-level buttons:
  - [x] Pending Payments
  - [ ] Provision Orders
  - [x] Wallet Charges
  - [x] Tickets
  - [x] Broadcast
  - [x] Sales Report
  - [ ] Customers
  - [ ] Plans
- [x] Add pending payment list screen.
- [ ] Add payment detail screen with approve/reject buttons.
- [ ] Add provision order screen with confirm button.
- [x] Add wallet charge list and approve button.
- [ ] Add ticket admin list/detail/reply/close buttons.
- [x] Add reseller broadcast compose FSM with preview/confirm.
- [ ] Add sales report preset buttons:
  - [x] Today
  - [x] 7 days
  - [x] 30 days
  - [ ] Custom
- [ ] Keep seller admin slash commands as shortcuts.

### FSM And Navigation Architecture

- [x] Add FSM state groups for master reseller flows.
- [x] Add FSM state groups for master seller bot flows.
- [ ] Add FSM state groups for master panel flows.
- [ ] Add FSM state groups for master plan/discount/broadcast/settings flows.
- [ ] Add FSM state groups for seller purchase/renew/wallet/ticket flows.
- [x] Add central cancel handler.
- [x] Add stale-state recovery: Home/Cancel should clear state.
- [ ] Add permission checks to every callback handler.
- [x] Add callback data size tests.
- [ ] Add tests for critical FSM transitions.

### Visual Polish Rules

- [ ] Use concise titles and sections instead of long paragraphs.
- [ ] Keep IDs visible but compact.
- [ ] Use consistent status icons and labels.
- [ ] Use confirmation screens for destructive actions.
- [ ] Use message edits for menu navigation where possible to reduce chat spam.
- [ ] Use new messages for important receipts, QR codes, and final confirmations.
- [ ] Truncate logs and long broadcasts safely.
- [ ] Avoid exposing secrets in any UI screen or log output.

### Phase 7 Deliverables

- [ ] Master bot can be operated mostly through buttons.
- [ ] Seller buyer flows can be operated mostly through buttons.
- [ ] Seller admin flows can be operated mostly through buttons.
- [ ] Existing slash commands still work.
- [ ] Tests cover keyboard builders, callback parsing, permission checks, and critical FSM flows.
- [ ] Production deploy verifies the new button UX starts without polling/runtime errors.
