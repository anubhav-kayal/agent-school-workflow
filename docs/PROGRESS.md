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
- feat(models): kb_facts, creatives, agent_runs, proposed_actions, audit_log, reports; ads.creative_id. Next: Alembic + initial migration.
- chore(db): Alembic async env + initial migration (round-trip verified, alembic check clean). Next: Pydantic schemas.
- feat(schemas): Pydantic v2 schemas (Indian mobile → E.164, paise, consent required, extra fields forbidden). Next: demo seed.
- feat(seed): idempotent fake demo school (users, ad accounts, 11 KB facts incl. 1 unverified, 14 days of IST slots). Next: model integrity tests.
- test(models): lead hard-delete cascade, slot delete protection, migration/model drift check on scratch DB. M1 complete. Next (after go-ahead): M2 leads + WhatsApp assistant.
- docs: WhatsApp template drafts (7 templates, en + hi, variables, buttons, expected category) for Meta submission. Next: INR/IST formatting.
- feat(formatting): Indian number grouping, ₹ lakh/crore, IST slot labels (en/hi, ≤20 chars). Next: WhatsApp adapter + 24h window.
- feat(adapters): WhatsApp adapter policy (opt-out, 24h window, approved templates, button limits) + fake transport. Next: Cloud API transport.
