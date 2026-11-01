# AdmissionPilot — Architecture (v1)

## Shape

```
 Meta / Google / WhatsApp webhooks ──► FastAPI (verify, dedupe, persist, enqueue, 200)
                                              │
                                              ▼
                         Redis + arq workers (jobs, cron schedules, retries)
          ┌──────────────┬───────────────┬──────────────┬────────────────┐
          ▼              ▼               ▼              ▼                ▼
   Assistant (Haiku)  Monitor        Optimizer      Creative/Reporter  Strategist
   deterministic      rules in code  pre-gate in    (Sonnet, Batch)    (Opus, Batch)
   router first       → Haiku triage code → Sonnet
          │              │               │              │                │
          └──────────────┴──────► proposed_actions ◄────┴────────────────┘
                                         │
                                 guardrails/executor ── audit_log
                                         │  (DRY_RUN default)
                                         ▼
                         adapters/* (real) | adapters/fakes/* (tests)
                                         │
                                 PostgreSQL 16 (source of truth)
```

## Layers

- **adapters/** — one interface per external API (Meta Marketing, Meta leadgen, Meta CAPI, Google Ads, Google conversions, WhatsApp, Anthropic). Each has a fake in `adapters/fakes/`. Tests only ever use fakes or `respx`. API versions come from config.
- **metrics/** — pure Python over DB rows: KPIs, anomaly rules, agent summaries. LLMs never compute numbers.
- **agents/** — `base.py` wraps the Anthropic SDK: model/effort from config, prompt caching, tool loop with max iterations, token budget, retries, Pydantic validation, `agent_runs` logging with cost in USD and INR. Prompts are markdown files in `agents/prompts/`.
- **guardrails/** — `rules.py` (pure functions, fully unit tested) and `executor.py` (the only code path that writes to ad platforms). Every proposal ends in an audit entry: applied, rejected, blocked (with rule) or dry_run.
- **webhooks/** — signature checks, parsing, idempotent persistence, enqueue. No business logic or external calls inline.
- **jobs/** — arq worker and cron schedules (Asia/Kolkata).
- **web/** — Jinja2 + HTMX + Tailwind CDN dashboard, session auth, role checks.

## Data principles

- Money in integer paise; timestamps `timestamptz` UTC; display in IST.
- Idempotency through unique constraints on external IDs (`wa_message_id`, `(school_id, external_lead_id)`, `(platform, external_id)`, `(platform, level, external_id, hour)`) and `INSERT … ON CONFLICT`.
- Personal data minimised: lead stores name, phone, grade interest, language, consent + source, opt-out time. Admin deletion scrubs PII and keeps anonymous funnel counts.
- Secrets only in env vars; `ad_accounts` stores a credentials *reference* (env var name), never a token.

## Cost and performance design

### 1. Code before LLM
| Event | Handled by | LLM? |
|---|---|---|
| New lead | First-contact WhatsApp template via arq job (60 s SLA) | No |
| Parent sends "STOP"/"unsubscribe"/"बंद" | Keyword router → opt-out | No |
| Parent taps a visit-slot button | Router → `book_visit` | No |
| Counselor taps status button | Router → `lead_events` | No |
| Reminders | Scheduled template sends | No |
| Parent free-text question | Assistant agent (Haiku) | Yes |
| Hourly monitor, no rule fired | Code only | No |
| Hourly monitor, rule fired | Haiku writes severity + alert | Yes |
| Optimizer, too little data / all in learning / summary unchanged | Pre-gate logs `no_action` | No |

### 2. Prompt caching
Request order: `tools` (fixed, sorted) → static system prompt → per-school verified KB block (explicit `cache_control` breakpoint) → conversation (automatic caching on the tail).
- Byte-stable prefix: no timestamps or IDs before the breakpoint; KB serialised with `sort_keys=True` and ordered by `(topic, key)`.
- KB block changes only when a verified fact is edited.
- TTL: 5 minutes by default; 1 hour for low-traffic schools' assistant prefix (configurable).
- `cache_read_tokens` and `cache_write_tokens` are logged per run; the cost page shows hit rate.

### 3. Batch API (−50 %)
Strategist, Reporter and Creative copy generation are single-shot and not latency sensitive, so they run through the Message Batches API and results are collected by a polling job. Assistant, Monitor and Optimizer stay synchronous.

### 4. Models and effort
| Agent | Model (config) | Effort | Output |
|---|---|---|---|
| Assistant | claude-haiku-5-5 | low | text + tools |
| Monitor triage | claude-haiku-5-5 | low | structured output |
| Optimizer | claude-sonnet-5-5 | medium | tools (`strict: true`, `tool_choice: auto`) |
| Creative | claude-sonnet-5-5 | medium | structured output |
| Reporter | claude-sonnet-5-5 | medium | structured output (markdown + numbers used) |
| Strategist | claude-opus-5-5 | high | structured output |

Current Opus/Sonnet models reject forced `tool_choice` and sampling params, so JSON results use structured outputs and tool agents use `auto` with `strict` schemas.

### 5. Budgets
- Per run: max tool iterations, max output tokens, token budget.
- Per school per month: LLM budget with an alert at 80 % and a hard stop at 100 % (assistant falls back to escalation).

### 6. Throughput
- Webhooks: verify → dedupe → persist → enqueue → 200 (target < 100 ms).
- Async SQLAlchemy (asyncpg) and shared httpx clients with pooling.
- Central Redis token-bucket rate limiter per platform and ad account; exponential backoff on throttling; Google Ads daily ops counter.
- Insights sync is incremental (re-pull last 3 days for attribution restatement) with upserts. `metrics_daily` rollups feed the dashboard and summaries.

## Safety rails
- `DRY_RUN=true` globally and per school; the executor logs exactly what it would do and calls nothing.
- Kill switch (global + per school) blocks all writes.
- Assistant states only verified KB facts; anything else → "a counselor will confirm" + escalation.
- Reporter output is checked so every number in the report appears in its input.
