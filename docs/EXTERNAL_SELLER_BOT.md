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
