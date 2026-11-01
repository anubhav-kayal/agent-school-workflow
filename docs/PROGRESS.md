# Progress

- docs: PLAN and ARCHITECTURE written. Next: M0 scaffold (pyproject, tooling).
- chore: pyproject (uv), ruff, mypy, pytest config. Next: typed settings + pricing tables.
- feat(config): typed settings, per-agent model/effort/budgets, pricing (TO VERIFY), .env.example. Next: FastAPI app + /health.
- feat(app): FastAPI factory, /health + /health/ready, async engine/session. Next: docker-compose + Makefile.
- chore: docker-compose (postgres 16, redis 7, test DB) + Makefile. Next: CI workflow.
- ci: GitHub Actions lint + test with Postgres/Redis services. M0 complete. Next: M1 models.
- fix(dev): compose on host ports 5433/6380 to avoid clashing with a native Postgres. Next: M1 models.
- feat(models): base + naming convention, schools, guardrail_configs, users, ad_accounts; DB test fixtures. Next: ads mirror + metrics tables.
- feat(models): campaigns/ad_sets/ads mirrors, metrics_hourly + metrics_daily with upsert keys. Next: leads, events, conversations, visit slots.
- feat(models): leads (consent, opt-out, deletion, attribution), lead_events (idempotency key), conversations, messages, visit_slots, visit_bookings. Next: KB, creatives, agent runs, proposals, audit, reports.
