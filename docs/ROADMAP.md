# Roadmap

## Phase 0 - Inventory And Decisions

- [x] Inspect existing folders.
- [x] Identify reusable source project: `panel_configs`.
- [x] Identify server deployment reference: `my-servers`.
- [x] Create clean platform folder and AI handoff docs.
- [x] Confirm which server will host the master platform. Target: `server-04`.
- [ ] Confirm domain/subdomain for bot webhook mode if webhooks are preferred.
- [ ] Confirm whether bots should use polling first or webhook first.

Recommended first choice: polling for MVP, webhook later.

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
- [ ] Add/edit/disable reseller admins. Initial add/list commands exist.
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
