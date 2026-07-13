# Local infrastructure

This compose file is a local-only dependency baseline for PostgreSQL, Redis
and MinIO. It contains no production credentials, persistent volume, migration
or real family data. API wiring is deferred until the dependency lock and
module ADRs are approved.

```bash
docker compose -f infra/compose/compose.yml config
docker compose -f infra/compose/compose.yml up -d
docker compose -f infra/compose/compose.yml ps
```
