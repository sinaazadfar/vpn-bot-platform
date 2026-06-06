# Server Inventory

This project was created from a workspace with these relevant sources:

- `../my-servers/config.server-01.json`
- `../my-servers/config.server-02.json`
- `../my-servers/server-02.txt`
- `../my-servers/server-03.txt`
- `../my-servers/servers-01.txt`
- `../my-servers/ADMIN_CONTROLLER.md`
- `../my-servers/admin-controller`

No local `server-04` inventory file was found yet. `server-04` is still the chosen production deployment target.

Known deployment reference from existing docs:

- Marzban admin controller public URL: `https://panel.my11228.qzz.io:2098/`
- Server-02 controller app path: `/opt/marzban-admin-controller`
- Server-02 local controller port: `127.0.0.1:8010`
- Server-02 public HTTPS port: `2098`

Before production deployment, fill this table with non-secret operational facts:

| Name | Role | Public Domain | SSH Alias | App Path | Notes |
| --- | --- | --- | --- | --- | --- |
| server-01 | TBD | TBD | TBD | TBD | Existing config file present |
| server-02 | Marzban/admin-controller | `panel.my11228.qzz.io` | TBD | `/opt/marzban-admin-controller` | Existing controller reference |
| server-03 | TBD | TBD | TBD | TBD | Existing text file present |
| server-04 | VPN bot platform production host | TBD | `server-04` | `/opt/vpn-bot-platform` | Chosen deployment target; use `ssh server-04` |

## Deployment Target

Use `server-04` for production deployment when the platform is ready.

Required non-secret facts to fill before enabling deploy:

- Public IP or DNS name.
- SSH username for CI, unless using a self-hosted runner with SSH config.
- SSH alias: `server-04`.
- Confirm app path: `/opt/vpn-bot-platform`.
- Confirm Docker and Docker Compose are installed.
- Confirm outbound access to Telegram API and Marzban panels.

Required GitHub secrets:

- `DEPLOY_USER`: SSH user for server-04.
- `DEPLOY_SSH_KEY`: private key allowed to deploy to server-04.
- `DEPLOY_APP_DIR`: `/opt/vpn-bot-platform`.

Never commit:

- Telegram bot tokens
- Marzban admin passwords
- Marzban API tokens
- SSH private keys
- real database passwords
- payment gateway secrets
