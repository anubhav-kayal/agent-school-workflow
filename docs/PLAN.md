# AdmissionPilot — Plan

Success metric: **cost per campus visit** and **cost per admission** (never cost per lead alone).
Each commit: 150–250 changed lines (hard max 300; lockfiles, generated migrations, fixtures, fonts excluded).
`docs/PROGRESS.md` gets one line per commit.

## Assumptions (defaults chosen without blocking)

- Package manager: `uv` (`uv.lock` committed). Make targets wrap `uv run`.
- Money is stored as **integer paise** (`BIGINT`). Floats never touch money. INR formatting (`₹1,50,000`, `₹1.5 lakh`) in one helper.
- All timestamps are `timestamptz` in UTC; convert to `Asia/Kolkata` only at the edges (schedules, reports, WhatsApp text).
- Phones stored E.164. Seeds/tests use obviously fake numbers (`+9199999000xx`). Hashing (SHA-256) for CAPI / enhanced conversions happens at send time.
- Internal PKs are `bigint` identity; external IDs are `text` with unique constraints for idempotency.
- DB tests run against docker-compose Postgres (`admissionpilot_test`), each test in a rolled-back transaction. Pure unit tests need no DB.
- WhatsApp: direct Cloud API (no BSP). Report email: SMTP adapter with fake.
- Pricing table pre-filled with published list prices, each marked `TO VERIFY`. USD→INR rate is a config value.
- Repo is local until a GitHub remote is provided; the CI workflow is committed anyway.
- LLM per-school monthly budget: alert at 80 %, hard stop at 100 % (assistant falls back to template + human escalation).

## Cost & performance decisions (details in ARCHITECTURE.md)

1. Code decides before the LLM: template first-reply, STOP, button replies, reminders, anomaly rules and an Optimizer pre-gate are deterministic. LLM runs only when judgement or language is needed.
2. Prompt caching: tools → static system prompt → per-school verified KB (breakpoint) → conversation. Byte-stable prefixes (sorted JSON, no timestamps).
3. Batch API (−50 %) for Strategist, Reporter and Creative copy generation.
4. Model + effort per agent in config; structured outputs instead of forced tool choice.
5. Compact pre-computed JSON summaries; token budget and max tool iterations per run.
6. Webhooks persist + enqueue + 200 fast; incremental metric sync with upserts; daily rollups for dashboards.

## LLM provider: OpenAI (proposal, awaiting approval)

Sources: https://developers.openai.com/api/docs/pricing ; model pages under
https://developers.openai.com/api/docs/models/ (read 2026-11-01). Prices USD per 1M tokens, Standard tier.

| Tier | Used by | Proposed model | Input | Cached input | Cache write (30m) | Output |
|---|---|---|---|---|---|---|
| tier_strategy | Strategist (Batch) | `gpt-6-astra` | 10.00 | 1.00 | 12.50 | 50.00 |
| tier_standard | Optimizer, Creative, Reporter | `gpt-6.1-sol` | 2.00 | 0.10 | 2.50 | 10.00 |
| tier_fast | Assistant, Monitor triage | `gpt-6-luna` | 0.10 | 0.01 | 0.125 | 0.50 |
| (fallback for tier_fast if Hindi < 90 %) | Assistant | `gpt-6.1-terra` | 1.00 | 0.05 | 1.25 | 5.00 |

- Batch API and Flex: 50 % of Standard, 24 h completion window.
- Long context: prompts over 272K input tokens pay 2x input/cache and 1.5x output for the whole request. Our prompts stay far below this.
- All four models: 1.05M context, 128K max output.
- Rough cost per assistant conversation (3 model calls, ~3K cached prefix + ~1.5K fresh input + ~300 output per call):
  - Luna: ≈ $0.0008 (≈ ₹0.07)
  - Terra: ≈ $0.009 (≈ ₹0.8)
  - Sol: ≈ $0.018 (≈ ₹1.5)
  - Evals will measure the real numbers.

## Milestones and commits

### M0 Scaffold
| # | Commit | ~Lines |
|---|---|---|
| 1 | docs: add PLAN and ARCHITECTURE | 280 |
| 2 | chore: add pyproject, ruff, mypy, pytest config | 120 |
| 3 | feat(config): typed settings, model + pricing tables, .env.example | 200 |
| 4 | feat(app): FastAPI app factory with /health and async db engine | 150 |
| 5 | chore: docker-compose and Makefile | 120 |
| 6 | ci: GitHub Actions lint + test | 80 |

### M1 Data model
| # | Commit | ~Lines |
|---|---|---|
| 7 | feat(models): base, schools, users, ad_accounts, guardrail_configs | 220 |
| 8 | feat(models): campaigns, ad_sets, ads, metrics_hourly, metrics_daily | 200 |
| 9 | feat(models): leads, lead_events, conversations, messages, visit_slots | 230 |
| 10 | feat(models): kb_facts, creatives, agent_runs, proposed_actions, audit_log, reports | 230 |
| 11 | chore(db): alembic async env + initial migration | 100 |
| 12 | feat(schemas): Pydantic v2 schemas | 200 |
| 13 | feat(seed): demo school seed (fake data) | 200 |
| 14 | test(models): constraints, idempotency, lead deletion | 180 |

### M2 Leads + WhatsApp assistant
| # | Commit | ~Lines |
|---|---|---|
| 15 | feat(formatting): INR / lakh formatting + IST helpers | 150 |
| 16 | feat(leads): idempotent lead service + lead_events | 200 |
| 17 | feat(webhooks): website form endpoint with consent capture | 180 |
| 18 | feat(adapters): Meta leadgen adapter interface + fake | 200 |
| 19 | feat(webhooks): Meta leadgen verify + signature + fetch lead | 220 |
| 20 | feat(adapters): WhatsApp adapter (template/text/buttons/list) + fake | 250 |
| 21 | feat(webhooks): WhatsApp inbound + status webhook, dedupe on wa_message_id | 230 |
| 22 | feat(jobs): arq worker, first-contact template job (<60 s SLA) | 200 |
| 23 | feat(assistant): deterministic router (STOP, slot buttons, counselor buttons) | 220 |
| 24 | feat(agents): base LLM client (caching, tool loop, budgets, retries) | 250 |
| 25 | feat(agents): agent_runs logging + cost estimation | 180 |
| 26 | feat(assistant): tools (facts, slots, book, language, escalate, not_interested) | 250 |
| 27 | feat(assistant): system prompt + agent wiring | 200 |
| 28 | feat(assistant): visit reminders (day-before, morning-of) | 180 |
| 29 | feat(assistant): counselor alert with status buttons → lead_events | 200 |
| 30 | feat(privacy): admin lead deletion (DPDP) | 150 |
| 31 | test: end-to-end lead → visit → counselor → event integration | 220 |
| 32 | feat(evals): runner + scoring + results output | 230 |
| 33 | feat(evals): 15 assistant scenarios (YAML, not counted) | 60 |

### M3 Ads sync + metrics
| # | Commit | ~Lines |
|---|---|---|
| 34 | feat(ratelimit): Redis token bucket per platform/account + Google ops counter | 200 |
| 35 | feat(adapters): Meta Marketing read adapter + fake | 250 |
| 36 | feat(adapters): Google Ads GAQL read adapter + fake | 250 |
| 37 | feat(sync): structure sync (campaigns/ad sets/ads) upserts | 200 |
| 38 | feat(sync): incremental hourly insights sync (3-day restatement) | 220 |
| 39 | feat(metrics): daily rollups | 150 |
| 40 | feat(metrics): KPI module (cost/visit, cost/admission, funnel) + tests | 250 |
| 41 | feat(metrics): agent summaries (1/3/7 day per ad set) + tests | 230 |
| 42 | feat(jobs): hourly sync schedule | 120 |

### M4 Dashboard + Reporter
| # | Commit | ~Lines |
|---|---|---|
| 43 | feat(web): session auth + roles | 250 |
| 44 | feat(web): base layout (Jinja2/HTMX/Tailwind CDN) | 180 |
| 45 | feat(web): school overview KPIs, funnel, 30-day chart | 250 |
| 46 | feat(web): leads inbox + status updates | 230 |
| 47 | feat(web): KB editor with verified toggle | 200 |
| 48 | feat(web): agent activity feed + cost page | 220 |
| 49 | feat(web): settings (guardrails, autonomy, dry-run, kill switch) | 220 |
| 50 | feat(reporter): weekly metrics input + Batch API submission | 230 |
| 51 | feat(reporter): number-provenance validator + delivery (dry-run aware) | 220 |

### M5 Creative studio + approvals
| # | Commit | ~Lines |
|---|---|---|
| 52 | feat(creative): copy generation via Batch + structured output | 250 |
| 53 | feat(creative): validator (claims, limits, superlatives, duplicates) | 230 |
| 54 | feat(render): Playwright renderer + Noto fonts | 180 |
| 55 | feat(render): 3 HTML templates (EN/HI/bilingual) | 220 |
| 56 | feat(web): approvals queue for creatives | 220 |
| 57 | feat(creative): WhatsApp approval to school approver | 200 |

### M6 Guardrails + executor + Optimizer
| # | Commit | ~Lines |
|---|---|---|
| 58 | feat(guardrails): rules (pct change, edit frequency, caps, kill switch, autonomy) | 250 |
| 59 | test(guardrails): full rule coverage | 250 |
| 60 | feat(guardrails): executor + audit log + dry-run | 250 |
| 61 | feat(adapters): Meta/Google write methods (budget, status, create ad) + fakes | 250 |
| 62 | feat(optimizer): deterministic pre-gate (no-data / learning / unchanged) | 180 |
| 63 | feat(optimizer): agent, tools, prompt, proposals | 250 |
| 64 | feat(web): proposals in approval queue → executor | 200 |
| 65 | feat(evals): 8 optimizer scenarios | 100 |

### M7 Conversion feedback
| # | Commit | ~Lines |
|---|---|---|
| 66 | feat(adapters): Meta CAPI for CRM + fake | 220 |
| 67 | feat(adapters): Google offline / enhanced conversions for leads + fake | 230 |
| 68 | feat(conversions): outbox + retry queue + dedupe | 230 |
| 69 | test(conversions): stage change → queued → synced timestamps | 180 |

### M8 Monitor + Strategist + cost tracking
| # | Commit | ~Lines |
|---|---|---|
| 70 | feat(metrics): anomaly rules + tests | 250 |
| 71 | feat(monitor): hourly job, LLM triage only when rules fire, Optimizer trigger | 220 |
| 72 | feat(strategist): Batch API weekly plan + approval | 250 |
| 73 | feat(costs): per-school monthly LLM budget, 80 % alert, hard stop | 200 |
| 74 | docs: RUNBOOK | 150 |

## Open questions

1. GitHub remote / org for CI?
2. WhatsApp: direct Cloud API (assumed) or a BSP (Gupshup, Interakt…)?
3. Report email provider (assumed generic SMTP)?
4. Exact pricing numbers and the USD→INR rate to use.
5. Hosting region (AWS ap-south-1 vs GCP asia-south1) — no infra code now.
6. Approve the OpenAI tier → model mapping above.

## To verify (API details, checked against current docs before each adapter)

- Meta Graph API version; insights fields and hourly breakdown (`hourly_stats_aggregated_by_advertiser_time_zone`); ad set `daily_budget` units (minor currency units).
- Meta leadgen webhook payload shape; `X-Hub-Signature-256` HMAC-SHA256 with app secret.
- Meta Conversions API for CRM: event names per lead stage, `lead_id` placement, `action_source` = `system_generated`.
- Google Ads API version; GAQL fields for campaign metrics; `CampaignBudgetService` mutate; offline conversion upload with `gclid` vs enhanced conversions for leads (hashed email/phone); daily operations limits.
- WhatsApp Cloud API: template send payload, interactive reply buttons (max 3), list messages (max 10 rows), 24-hour window rules, status webhooks.
- Anthropic: minimum cacheable prefix per model, cache TTL pricing, Batch discount, per-model prices.
