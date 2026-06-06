# Webhook Mode

Current production decision: use polling first.

Webhook mode should be enabled only after these are ready:

- A stable domain or subdomain for the platform.
- HTTPS certificate renewal through nginx, Caddy, or another reverse proxy.
- A small HTTP app that receives Telegram webhook updates and dispatches them to aiogram.
- Per-seller webhook paths or hostnames so seller bots do not collide.

Polling remains the default because it is simpler, works behind SSH-only deployment, and is already verified on `server-04`.

Suggested future domain shape:

```text
master.example.com
seller-<seller_bot_id>.example.com
```

or path-based:

```text
bot.example.com/webhook/master
bot.example.com/webhook/seller/<seller_bot_id>
```
