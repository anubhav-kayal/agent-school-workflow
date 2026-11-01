# AdmissionPilot — Architecture (v1)

## Shape

```
 Meta / Google / WhatsApp webhooks ──► FastAPI (verify, dedupe, persist, enqueue, 200)
                                              │
                                              ▼
                         Redis + arq workers (jobs, cron schedules, retries)
          ┌──────────────┬───────────────┬──────────────┬────────────────┐
          ▼              ▼               ▼              ▼                ▼
   Assistant (fast)   Monitor        Optimizer      Creative/Reporter  Strategist
   deterministic      rules in code  pre-gate in    (standard, Batch)  (strategy, Batch)
   router first       → fast triage  code → standard
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

- **adapters/** — one interface per external API (Meta Marketing, Meta leadgen, Meta CAPI, Google Ads, Google conversions, WhatsApp, Email). Each has a fake in `adapters/fakes/`. Tests only ever use fakes or `respx`. API versions come from config.
- **metrics/** — pure Python over DB rows: KPIs, anomaly rules, agent summaries. LLMs never compute numbers.
- **agents/** — agents never import an SDK. `agents/llm/` holds a small `LLMProvider` interface and the `OpenAIProvider`. `base.py` runs the loop: tier/effort from config, prompt caching, tool loop with max iterations, token budget, retries, Pydantic validation, `agent_runs` logging with cost in USD and INR. Prompts are markdown files in `agents/prompts/`.
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
| Parent free-text question | Assistant agent (tier_fast) | Yes |
| Hourly monitor, no rule fired | Code only | No |
| Hourly monitor, rule fired | tier_fast model writes severity + alert | Yes |
| Optimizer, too little data / all in learning / summary unchanged | Pre-gate logs `no_action` | No |

### 2. Prompt caching (OpenAI)
On GPT-5.6 and later models caching is **automatic**: no code change needed.
Source: https://developers.openai.com/api/docs/guides/prompt-caching.md
- Prompts of at least 1,024 tokens are eligible.
- Cache reads are billed at 0.1x input (0.05x on gpt-6.1-sol and gpt-6.1-terra).
- Cache writes are billed at 1.25x input (default 30-minute TTL) or 2.5x (12-hour TTL, `prompt_cache_options.ttl`).
- An explicit mode (`prompt_cache_options.mode="explicit"` + breakpoints) exists. We start with automatic.
- `prompt_cache_key` is set to `school:<id>:<agent>` for per-tenant accounting; routing doesn't need it on these models.
- Above about 15 requests/min on one prefix, requests may land on machines without the cache. Not a concern at our volume.

Layout either way: tools (fixed order) → static system prompt → school's verified KB (sorted JSON) → conversation. No timestamps or IDs before the conversation. `usage.input_tokens_details.cached_tokens` goes into `agent_runs.cache_read_tokens`.

### 3. Batch API (−50 %)
Source: https://developers.openai.com/api/docs/guides/batch.md
- 50 % of Standard price. The completion window is fixed at 24 h. Input is JSONL with a `custom_id` per line, one model per file, and `/v1/responses` is supported.
- Strategist, Reporter and weekly Creative generation use it.
- The weekly report batch is submitted Sunday ~20:00 IST. If it isn't complete by Monday 08:30 IST, the job cancels it and regenerates through the normal API so delivery at 09:00 holds.
- Urgent creative requests (Optimizer `request_creatives` with high urgency) use the normal API.

### 4. API, models and parameters
- **API:** the **Responses API** via the official `openai` Python SDK (3.42).
  - OpenAI recommends Responses for new projects (https://developers.openai.com/api/docs/guides/migrate-to-responses.md).
  - GPT-6 models need it for tool calling (https://developers.openai.com/api/docs/guides/latest-model.md).
- **Tools:**
  - Function tools with `strict: true` and `additionalProperties: false`; optional fields are typed nullable.
  - We resend the full input list (no server-side state) with `store=false`.
  - Model output items, including reasoning items, are appended before our `function_call_output` items.
  - Source: https://developers.openai.com/api/docs/guides/function-calling.md
- **Structured outputs:** `responses.parse(text_format=PydanticModel)` (https://developers.openai.com/api/docs/guides/structured-outputs.md).

| Tier | Model | Agents | Effort |
|---|---|---|---|
| tier_fast | gpt-6-luna | Assistant, Monitor triage | low |
| tier_standard | gpt-6.1-sol | Optimizer, Creative, Reporter | medium |
| tier_strategy | gpt-6.1-sol (Batch) | Strategist | high |

**Parameter behaviour** (https://developers.openai.com/api/docs/guides/latest-model.md, https://developers.openai.com/api/docs/guides/reasoning.md):
- `temperature`, `top_p` and `top_logprobs` are rejected unless `reasoning.effort` is `none`. Only Luna and Terra accept `none`. We never send sampling parameters.
- Effort levels:
  - Sol: `low` … `max`. It has no `none`, and `minimal` maps to `low`.
  - Luna and Terra: also accept `none`.
  - Default is `medium`, so we always set it.
- `max_output_tokens` includes reasoning tokens. Running out returns `status="incomplete"`, which `base.py` treats as an error and retries once with more room.

### Data handling (OpenAI API)
Source: https://developers.openai.com/api/docs/guides/your-data.md (read 2026-11-01)
- API inputs and outputs are **not used for training** unless the organisation opts in.
- Abuse-monitoring logs are kept up to **30 days**.
- Zero Data Retention or Modified Abuse Monitoring requires OpenAI approval.
- Responses are stored by default. We send **`store=false`** on every call, so OpenAI does not keep application state.
- **India:** the `in` region offers data storage at rest only. **Inference runs outside India** (regional processing exists only for the US, EU and UAE).
  - Parents' messages are therefore processed abroad. This is a DPDP consideration for the school's privacy notice and consent text.
  - We send the minimum needed: first name, grade and message text. Never the phone number.
  - Applying for ZDR is an open item.

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
