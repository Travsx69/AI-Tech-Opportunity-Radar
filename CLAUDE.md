# AI Tech Opportunity Radar — project context

Local-first Python (stdlib only, Python 3.11 at `%APPDATA%\uv\python\cpython-3.11-windows-x86_64-none\python.exe`, overridable with `RADAR_PYTHON`) service that discovers AI tools, open-source projects, models, research, business signals, and jobs from free sources. It AI-analyzes a capped subset and serves a dashboard and API on :8787.

## Architecture
- `opportunity_radar/registry.py`: builds `SourceSpec`s from `config/sources.json`. Zero-cost gate: `requires_payment` or `requires_credentials` forces a source to disabled.
- `sources.py`: shared `fetch` (timeout, backoff on 429/5xx), `canonical_url`, `redact`, and the HF/RSS/Remotive adapters. `github.py` and `hackernews.py` hold the original adapters.
- `pipeline.py:run_discovery`: per-source and per-request isolation, `min_interval_minutes` skipping, request gaps, dedup, `discovered_items` index, analysis capped at `max_analyzed`. `run_github_discovery` is the legacy wrapper used by tests.
- `core.py`: normalization, 3-stage dedup, relevance selection (word-boundary terms, one slot per source).
- `store.py`: SQLite at `data/radar.db`. Migrations are additive `ALTER TABLE` and `CREATE IF NOT EXISTS` only; never recreate tables.
- `service.py`: HTTP endpoints `/`, `/health`, `/run` (lock, 409 on overlap), `/api/opportunities|items|runs|sources`. `dashboard.py` holds the inline HTML.
- `app.py`: `RadarConfig.from_env()` uses `config/sources.json`. A `RadarConfig` built directly has `sources_config=None`, which means legacy GitHub(+HN) only, and tests rely on that to avoid the network.
- AI: Ollama or OpenRouter, chosen by machine-scope env vars `AI_PROVIDER` and `OPENROUTER_*`. **Do not change the provider or model.**

## Deployment (do not change without approval)
- `start-radar.ps1` starts `serve.py` hidden (0.0.0.0:8787), so n8n in Docker can reach it at `host.docker.internal:8787`.
- n8n workflow `13oxoQeASaKIsu74` is LIVE and active, daily at 10 PM Asia/Manila (trigger "Daily at 10 PM", `0 22 * * *`), posting to Discord. The repo file mirrors it. Regenerate the Code node with `python scripts/sync_workflow_code.py` after editing `scripts/discord_digest.js`. Push code or schedule changes with `python scripts/push_workflow_formatter.py` (a dry run by default; `--apply` drafts, verifies, then publishes).
- The website (the separate `built-by-msb` project, a Cloudflare Worker with D1) gets data only through `connector/radar_connector.py`, which reads `/api/opportunities`, `/api/runs`, and `/api/sources`. Keep those field names. The Worker stores only the five legacy source fields.

## Conventions
- Stdlib only, type hints, `from __future__ import annotations`, and injectable collectors (`request_json`, `fetch_json_fn`) for tests.
- Never invent metrics: use None when a source has no value (for example `github_stars` for non-GitHub, or job salary).
- All stored and served error text goes through `redact()`.
- Tests: `python -m unittest discover -s tests` (92) and `node --test tests/test_discord_digest.js` (12). Mock all HTTP.

## Status (2026-10-16)
- Done: multi-source upgrade. A bounded live check collected real data from GitHub, HN, HF, RSS, and Remotive with no AI calls.
- 2026-10-16: the :8787 service was restarted on the new code and the DB migrated in place (backup at `data/radar.db.pre-multisource-20261016.bak`). 24 opportunities and 8 runs were preserved. The old service ran elevated. In this restart, `start-radar.ps1` started from an admin shell left nothing listening (cause unknown). The service now runs unelevated, started with `Start-Process` directly.
- 2026-10-16: the new Discord formatter was pushed to live n8n with `scripts/push_workflow_formatter.py --apply`, which builds from the published version, PUTs with `publishIfActive=false`, reads back, then publishes with `POST /activate {versionId}`. The published version went from 1ea2ef1c to 364460b2, and only `jsCode` changed. Rollback copies are in `workflows/backup/`.
- n8n 2.37 note: the draft (`versionId`) and the published version (`activeVersionId`) can differ. A plain PUT re-publishes immediately.
- Confirmed 2026-10-20: missed 6 AM n8n runs happen because the PC is shut down at 6 AM Manila (Windows event 1074 shows Start-menu shutdowns). Executions 36–39 match exactly the days the PC was on. n8n does not catch up missed schedules. The user chose to move the schedule to 10 PM Manila (the PC was on at 10 PM on 8 of 12 sampled days). It still misses nights when the PC is off; the alternative was an hourly trigger plus a once-per-day guard.
- Known limitations: the service has CORS `*` and no auth (keep it local and firewalled). There is no HTTP ETag caching (polling intervals cover it). The HN rate limit is undocumented. Remotive jobs are filtered by job title keywords only.
