# AI Tech / Opportunity Radar

> **Multi-source upgrade (2026-10-16).** Discovery now covers GitHub, Hacker News, Hugging Face Hub, RSS/Atom feeds, and Remotive jobs, all free and keyless. See [Sources](#sources-free-only) below. The sections after it describe the original GitHub MVP and remain accurate for the service, n8n, and OpenRouter/Ollama setup.

## Sources (free only)

Configured in `config/sources.json` (add feeds/queries there; no pipeline changes needed). Access terms were checked on 2026-10-16.

| Source | Access | Polling | Notes |
|---|---|---|---|
| GitHub | REST search, optional free token | every run | Unchanged queries; 403 rate limit reported, not retried |
| Hacker News | Algolia search, no key | every run, 6 queries, `points>=5` | No official rate limit is published |
| Hugging Face | Hub API, no token (500 req / 5 min per IP) | at most every 6 h, 6 searches, 1 page each | Likes and downloads are signals, not proof of value |
| RSS/Atom | 10 validated official feeds | at most every 3 h, 8 items/feed, 21 days | DeepMind (not parseable XML) and Microsoft AI (HTTP 410) are disabled |
| Remotive | Public jobs API, no key | at most every 6 h, 2 searches, 35 s apart | Terms: ≤4 fetches/day, credit and link to Remotive, no resubmitting jobs to third-party job sites. Jobs are indexed only, never AI-analyzed, and are not part of `/api/opportunities` (so they are not synced to the website) |
| Product Hunt | **Disabled** | — | Needs a token, and the API terms prohibit commercial use without permission |

How a run works: every enabled source runs independently (one failing request only degrades its source). All records go to the `discovered_items` index, which tracks first-seen and last-seen times. Records are deduplicated by source ID, then canonical URL, then near-identical titles across sources, and supporting sources are kept as attribution. Then **at most `RADAR_MAX_ANALYZED` items (default 5) are AI-analyzed per run, the same as before**. Each source's best fresh item gets a slot first. A run is `success`, `partial_failure`, or `failed` (no source collected anything).

API additions (existing contracts kept): `/api/sources` returns the original five fields plus `enabled`, `healthy`, `collecting`, `last_success_at`, `indexed_items`, and a `summary` with configured, enabled, healthy, and collecting counts. `/api/opportunities?type=` filters by type. `/api/items?type=&source=&search=` lists the full index, including jobs.

n8n/Discord: `workflows/github-mvp.n8n.json` was rebuilt from the live export (`data/workflow-live.json`: same nodes and credential), and its formatter was regenerated from `scripts/discord_digest.js` with `python scripts/sync_workflow_code.py`. The formatter now labels each link by source and marks items as new or updated. It adds supporting links and a footer for partial failures. It stays silent on clean empty runs and on 409 overlapping-run responses. Pushed to live n8n on 2026-10-16 with `python scripts/push_workflow_formatter.py --apply` (run it without `--apply` for a dry run). On 2026-10-20 the schedule moved from 6 AM to 10 PM Manila, because the PC is usually off at 6 AM and n8n does not catch up missed runs. The script changes only the Code node and the schedule trigger, writes rollback copies to `workflows/backup/`, and verifies the result before and after publishing.

A tested local-first MVP that discovers GitHub repositories related to AI agents, automation, n8n, MCP, local LLMs, LLM applications, developer tools, and computer-use tooling. It normalizes and deduplicates candidates, applies deterministic relevance filtering, analyzes selected items with local Ollama/Qwen, validates structured output, and stores records in SQLite plus JSON.

## Architecture

```text
n8n Manual/Schedule Trigger
        |
        v
POST http://host.docker.internal:8787/run
        |
        v
GitHub Search API (4 focused queries)
        |
        v
Normalize -> in-batch dedupe -> relevance score/limit
        |
        v
Persistent dedupe against SQLite
        |
        v
Ollama qwen3.5:9b structured analysis
        |
        v
Schema validation -> SQLite -> opportunities.json
        |
        v
n8n digest formatter -> Discord webhook credential
```

The n8n workflow is intentionally thin. The Python service owns the testable discovery and analysis pipeline; n8n supplies manual and scheduled orchestration. This avoids changing the existing n8n Docker Compose configuration or mounting new paths into its data volume.

## Current MVP scope

Implemented:

- GitHub repository search using four focused queries
- Normalization into a common source record
- In-batch and persistent deduplication by source ID and canonical URL
- Relevance filtering that favors topical fit and evidence of adoption without blindly rewarding keyword stuffing
- Local AI analysis through Ollama `qwen3.5:9b`
- Required structured fields:
  - `title`, `source`, `url`, `date_discovered`, `category`, `summary`
  - `what_it_does`, `why_it_matters`, `potential_use_for_us`
  - `business_opportunity`, `technical_opportunity`, `estimated_effort`
  - `recommended_next_action`, `evidence`, `confidence`
- Controlled opportunity categories and confidence values
- SQLite persistence and JSON export
- Graceful per-query and per-item failure handling
- Local HTTP service for n8n
- Inactive n8n workflow with manual/daily triggers and Discord digest delivery
- Explicit upstream failure reporting when the Radar service is unavailable or returns an invalid response

Not implemented yet: YouTube, Hacker News, or deep README/site research.

## Requirements

- Python 3.11+
- Ollama at `http://localhost:11434`
- Local model `qwen3.5:9b`
- n8n in Docker for workflow orchestration
- Internet access to `api.github.com`

No Python packages are required; the MVP uses the standard library.

## Run manually

From `C:\AI-Tech-Opportunity-Radar`:

```bash
python run.py
```

Limit AI analysis during a test:

```bash
python run.py --max-analyzed 1
```

Use an isolated output directory:

```bash
python run.py --data-dir data-verification --max-analyzed 1
```

Outputs:

- `data/radar.db` — canonical SQLite store
- `data/opportunities.json` — readable export of all stored reports

The command exits with code `0` when no collection or analysis failures occur and code `2` when the run completes with one or more recorded failures.

## Run the n8n-facing service

```bash
python serve.py
```

Endpoints:

- `GET http://localhost:8787/health`
- `POST http://localhost:8787/run`

The service prevents overlapping runs with an in-process lock. The current Docker n8n container can reach it at `http://host.docker.internal:8787`.

The service must be running before an n8n execution starts. Verify both boundaries before a manual run:

```bash
curl http://localhost:8787/health
docker exec ai-video-n8n node -e "fetch('http://host.docker.internal:8787/health').then(async r=>console.log(r.status,await r.text()))"
```

Expected results are `{"status": "ok"}` locally and HTTP `200` from the n8n container. For unattended scheduling, install the service as an OS-managed or container-managed process first; a terminal-bound `python serve.py` process is not sufficient for 24/7 operation.

## n8n workflow and schedule

Workflow file:

```text
workflows/github-mvp.n8n.json
```

It contains:

- Manual Trigger
- Schedule Trigger "Daily at 10 PM": `0 22 * * *` (was 8 AM, then 6 AM)
- Timezone: `Asia/Manila`
- HTTP Request to the radar service
- 10-minute timeout, two attempts, and continue-on-failure behavior
- Code node that validates the `/run` response and formats Discord-safe messages
- Discord node using the existing n8n Discord webhook credential

The HTTP node continues to the formatter when `/run` fails so Discord can receive an operational alert. The formatter requires numeric `collected` and `failed` fields plus a `reports` array before it treats a response as a successful Radar run. `ECONNREFUSED`, an n8n error item, or a malformed/missing response produces this status instead of invented zero statistics:

```text
RADAR SERVICE FAILURE
The Opportunity Radar service was unavailable or returned an invalid response.
GitHub discovery did not run.
Collection statistics are unavailable for this execution.
```

Successful responses retain the existing opportunity digest and no-new-opportunities formats.

The file defaults to inactive. After importing it into the actual n8n instance, inspect it and activate it when ready.

### Safe API import into the existing n8n instance

The inactive workflow was imported through the public n8n API and verified by a fresh read-back:

- Workflow ID: `13oxoQeASaKIsu74`
- Name: `AI Tech Opportunity Radar - GitHub MVP`
- Active: `false`
- Same-name workflow count after import: `1`

The importer remains idempotent by workflow name. Running it again will detect the existing workflow and will not create a duplicate:

```bash
export N8N_API_KEY='your-key-in-your-terminal-only'
python import_to_n8n.py
```

Optional override:

```bash
export N8N_BASE_URL='http://localhost:5678'
```

The importer:

1. Lists workflows and avoids creating a duplicate by name.
2. Creates the workflow inactive through `/api/v1/workflows`.
3. Reads the created workflow back by ID before reporting success.

### Manual end-to-end execution

Keep the workflow inactive and use **Execute Workflow** from the n8n editor. On the current local Docker installation, the equivalent verified CLI command is:

```bash
docker exec -e N8N_RUNNERS_BROKER_PORT=5680 ai-video-n8n n8n execute --id=13oxoQeASaKIsu74
```

Port `5680` avoids colliding with the running n8n instance's task-broker port. A manual execution runs the existing Manual Trigger; it does not activate the workflow or change the 10 PM schedule.

## Environment configuration

See `.env.example`. Supported variables:

- `GITHUB_TOKEN` or `GH_TOKEN` — optional but recommended
- `AI_PROVIDER` — `ollama` (default) or `openrouter`
- `OLLAMA_MODEL` — default `qwen3.5:9b`
- `OLLAMA_URL` — default `http://localhost:11434`
- `OPENROUTER_API_KEY` — required only when `AI_PROVIDER=openrouter`
- `OPENROUTER_MODEL` — default `openrouter/free`
- `OPENROUTER_TIMEOUT` — seconds, bounded to 1–300; default `120`
- `RADAR_DATA_DIR` — default `data`
- `RADAR_MAX_ANALYZED` — default `5`
- `RADAR_PER_QUERY` — default `5`
- `N8N_API_KEY` — required only for API import
- `N8N_BASE_URL` — default `http://localhost:5678`

Without a GitHub token, GitHub search is subject to a low anonymous search rate limit and may return HTTP 403. Failures are captured in the run result rather than silently ignored.

## Tests and real verification completed

Automated suite:

```bash
python -m unittest discover -s tests -v
```

Verified behaviors include normalization, canonical deduplication, relevance filtering, anti-keyword-stuffing ranking, strict structured AI output, malformed AI response handling, SQLite persistence, duplicate suppression across runs, GitHub API error handling, Ollama/Qwen `thinking` response compatibility, service endpoints, n8n API payload construction, Discord-safe message splitting, successful/no-new-opportunity digests, and unavailable/malformed Radar-service responses.

Real integration verification completed:

- Ollama model found: `qwen3.5:9b`
- Real GitHub collection and Qwen analysis produced structured opportunity records
- Canonical store currently contains real records
- Repeated runs detected persistent duplicates
- Service health responds with JSON
- Existing n8n Docker container reached the host service successfully
- Workflow `13oxoQeASaKIsu74` remains inactive in the existing n8n instance
- Live successful n8n execution collected 20 items, stored structured reports, and delivered a Discord digest
- Live service-unavailable execution converted `ECONNREFUSED` into an explicit Discord failure alert without zero statistics
- Service was restored and another successful n8n execution collected 20 items with `failed: 0`
- Existing Discord credential was reused without exposing or modifying its webhook URL

Validation evidence is retained in:

- `workflows/import-validation.log`
- `workflows/execution-validation.log`

## Current limitations

1. GitHub discovery uses repository metadata and descriptions, not full README or external market research.
2. Repository descriptions are publisher claims. The prompt requires attribution, but local-model analysis still needs human review before making business decisions.
3. Anonymous GitHub search rate limits are restrictive; a token is recommended for reliable scheduling.
4. The HTTP service has no authentication and should remain local/firewalled. Add authentication before exposing it on a VPS.
5. SQLite and the in-process run lock are appropriate for one local worker, not multiple distributed workers.
6. The workflow is active and runs at 10 PM Manila only while this PC is on; n8n does not catch up runs missed while it was off.
7. The local Radar service is not yet installed as an OS-managed or container-managed 24/7 service. It must be made durable before enabling the schedule.

## Next recommended implementation step

Install the Radar HTTP service as an OS-managed or container-managed process, then run a soak test while the n8n workflow remains inactive. Activate the 8 AM schedule only after service startup and restart behavior are proven. After stable GitHub runs, add Hacker News next because it has a free public API and lower credential complexity than YouTube. Add YouTube only after obtaining a YouTube Data API key and defining quota limits.
