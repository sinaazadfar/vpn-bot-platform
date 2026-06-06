# Monitoring And Alerting

## Health Checks

Run this on `server-04`:

```sh
APP_DIR=/opt/vpn-bot-platform sh /opt/vpn-bot-platform/deploy/healthcheck.sh
```

The check verifies:

- `postgres`, `master-bot`, and `worker` containers are running.
- Postgres accepts connections.
- Master bot is either recently polling or still running.

## Recommended Alerts

- Master bot container not running for 2 minutes.
- Worker container not running for 2 minutes.
- Postgres container not running or `pg_isready` fails.
- Disk usage above 80%.
- No successful Postgres backup in 24 hours.
- More than 5 `SellerBotStatus.ERROR` rows in 10 minutes.

## Useful Commands

```sh
cd /opt/vpn-bot-platform
docker compose ps
docker compose logs --tail 200 master-bot
docker compose logs --tail 200 worker
docker compose exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

## Future Metrics

The next production step is adding a small metrics exporter for:

- Bot update counts and rate-limit rejects.
- Orders by status.
- Payments by status.
- Provisioning failures by panel.
- Seller container health by reseller.
