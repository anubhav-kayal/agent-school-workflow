# AdmissionPilot

Agentic performance marketing for Indian schools and colleges during admission season.

Schools run Meta and Google ads to get admission enquiries. Most enquiries go cold because nobody
replies fast enough, parents ask the same questions again and again, and agencies optimise ads for
cheap leads instead of real admissions. AdmissionPilot replies to every parent on WhatsApp within
seconds, answers their questions from the school's verified facts, books campus visits, and keeps
the school's counselor in the loop. Every metric is measured as **cost per campus visit** and
**cost per admission**, not cost per lead.

> **Status:** milestones M0–M2 are done (lead intake + WhatsApp admission assistant + demo).
> Ads sync, dashboard, creatives, optimizer and conversion feedback are planned (M3–M8).
> Everything runs in **dry-run** by default: no real WhatsApp message is sent.

## What it does today

1. **Lead intake.** Leads arrive from Meta lead ads (signed webhook), the school website form, or
   a parent messaging the school's WhatsApp number. Duplicate webhook deliveries are ignored.
2. **First reply in seconds, no AI.** An approved WhatsApp template goes out immediately and
   `first_response_at` is recorded for every lead.
3. **Admission assistant (AI).** Answers parents on WhatsApp:
   - states **only verified facts** from the school's knowledge base (fees, transport, board…);
     anything missing or unverified → "a counselor will confirm" + counselor alert;
   - asks once for **English / हिंदी / Hinglish** and keeps to it (everyday Hindi in Devanagari,
     Hinglish = Hindi written in English letters);
   - offers campus-visit slots as tap-to-book buttons, understands "Saturday", reschedules;
   - escalates discounts, complaints and "talk to a human"; refuses prompt-injection tricks;
   - honours **STOP**: nothing is ever sent to that number again.
4. **Visit reminders** the evening before and the morning of the visit.
5. **Counselor alerts** on WhatsApp with four buttons (Visit booked / Visited / Admitted /
   Not interested) that update the lead's funnel status.
6. **Privacy (DPDP Act).** Consent source per lead, opt-out, and an admin command that erases a
   parent's personal data while keeping anonymous funnel counts.
7. **Cost tracking.** Every AI call logs model, tokens, cached tokens, latency and cost in USD
   and INR (currently about ₹0.01 per parent conversation).

## Quick start

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), Docker, `make`.

```bash
cp .env.example .env          # then set OPENAI_API_KEY (needed only for the AI replies)
make demo                     # Postgres + Redis, migrations, sample data, demo server
```

Open **http://localhost:8000/demo/chat**: a WhatsApp-style chat for a sample school. Type as the
parent; the real assistant replies. The side panel shows the counselor's alert with its status
buttons, the lead's timeline, and every AI call with its ₹ cost. The demo uses fake data and never
sends real WhatsApp messages; `/demo` returns 404 unless `DEMO_MODE=true`.

## Commands

| Command | What it does |
|---|---|
| `make up` / `make down` | Start / stop Postgres 16 and Redis 7 (host ports 5433 / 6380) |
| `make migrate` | Apply database migrations |
| `make seed` | Load the sample school (fake data; safe to re-run) |
| `make test` | Run the test suite (no network, no API costs) |
| `make lint` | ruff + format check + mypy |
| `make run` | API server with auto-reload on :8000 |
| `make worker` | Background worker (lead intake, inbound WhatsApp, reminders) |
| `make demo` | Everything above + the demo page |
| `make evals` | AI evals against the real model (costs a few rupees; never in CI). `TIER=tier_standard make evals` to compare models |
| `uv run python -m app.admin erase-lead <id> --actor <name>` | DPDP: erase a lead's personal data |

## How it works

```
Meta lead ads ─┐                      ┌─► first-response template (no AI)
Website form ──┼─► webhooks ─► queue ─┤
WhatsApp ──────┘   (verify,   (arq)   └─► conversation handler
                    dedupe)                 ├─ STOP / slot / language / counselor buttons → code
                                            └─ free text → admission assistant (AI)
                                                 └─ tools: verified facts, visit slots, booking,
                                                    language, escalate, not-interested
```

Design rules the code follows:

- **Code before AI.** Anything code can decide (first reply, STOP, button taps, reminders) never
  calls the model.
- **Facts only from the verified knowledge base.** Unverified facts never reach the model.
- **Every external API sits behind an adapter with a fake.** Tests cannot reach the internet: a
  guard fails any test that opens a non-local connection.
- **Dry-run by default.** WhatsApp sends are logged unless `DRY_RUN=false`, a token is set, and the
  template is approved by Meta.
- **Money in paise, times in UTC**, shown as ₹1,50,000 / "₹1.5 lakh" and IST at the edges.
- **AI behind a small provider interface** (`app/agents/llm/`). Today: OpenAI Responses API with
  model tiers in config: `tier_fast` = gpt-6-luna (assistant), `tier_standard` / `tier_strategy`
  = gpt-6.1-sol. Conversations are not stored at OpenAI (`store=false`).

## Project layout

```
app/
  adapters/      WhatsApp (policy + Cloud API), Meta lead ads; fakes/ for tests
  agents/        LLM provider interface, tool loop, costs, admission assistant, prompts/
  services/      leads, conversation, routing, knowledge base, visits, reminders,
                 counselor, privacy, templates
  webhooks/      Meta leads, WhatsApp, website form
  jobs/          arq worker + queue
  models/        SQLAlchemy models (schools, leads, events, messages, slots, KB, agent runs…)
  schemas/       Pydantic schemas
  web/           demo page (Jinja2 + HTMX + Tailwind)
  config.py      all settings: tiers, pricing, API versions, safety switches
migrations/      Alembic
evals/           scenarios/*.yaml, runner, scoring; results/ (git-ignored)
tests/           unit, webhook, job and end-to-end tests
docs/            PLAN, ARCHITECTURE, PROGRESS, whatsapp_templates
```

## Configuration

All settings come from environment variables (see `.env.example`); secrets live only in `.env`,
which is git-ignored. Important ones:

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | – | Needed for AI replies and evals |
| `DRY_RUN` | `true` | Log instead of sending WhatsApp messages / platform changes |
| `DEMO_MODE` | `false` | Enables `/demo/chat` (`make demo` turns it on) |
| `USD_TO_INR` | `84.0` | Rate used for ₹ cost reporting |
| `TIERS__TIER_FAST` etc. | see config | Override the model for a tier |
| `WHATSAPP_APPROVED_TEMPLATES` | `[]` | Templates Meta has approved (`name:lang`) |

## Quality

- **Tests:** ~170 automated tests covering webhooks, signatures, idempotency, the 24-hour WhatsApp
  window, opt-out, reminders, counselor flow, privacy, cost maths and a full
  lead → visit → counselor end-to-end flow. CI runs lint + tests on every push.
- **Evals:** 20 assistant scenarios (fees, missing facts, Hindi, Hinglish, angry parent, STOP,
  discount, competitor, unverified results, human hand-off, off-topic, booking, rescheduling,
  named days, prompt injection, language preference). Latest run: 20/20 on gpt-6-luna.

## Roadmap

| Milestone | Scope |
|---|---|
| M3 | Meta + Google Ads read sync, metrics, KPIs (cost per visit / admission) |
| M4 | Dashboard with roles; weekly report for the school |
| M5 | Creative studio: ad copy + images (English/Hindi), approval flow |
| M6 | Guardrails, single executor with audit log, Optimizer (recommend-only) |
| M7 | Conversion feedback to Meta CAPI and Google offline conversions |
| M8 | Hourly monitor, weekly strategist (Batch API), per-school AI budgets |

Details: [`docs/PLAN.md`](docs/PLAN.md) · [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) ·
[`docs/PROGRESS.md`](docs/PROGRESS.md) · [`docs/whatsapp_templates.md`](docs/whatsapp_templates.md)
