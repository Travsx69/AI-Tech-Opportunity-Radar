from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opportunity_radar.scoring import score_opportunity
from opportunity_radar.sources import canonical_url


class OpportunityStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with closing(self._connect()) as connection:
            # Base table
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS opportunities (
                    source_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL UNIQUE,
                    date_discovered TEXT NOT NULL,
                    report_json TEXT NOT NULL
                )
                """
            )
            
            # Runs table for observability
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    stopped_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    collected INTEGER DEFAULT 0,
                    stored INTEGER DEFAULT 0,
                    updated INTEGER DEFAULT 0,
                    failed INTEGER DEFAULT 0,
                    summary_json TEXT NOT NULL
                )
                """
            )

            # Source health tracking
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS source_health (
                    source_name TEXT PRIMARY KEY,
                    last_run_at TEXT NOT NULL,
                    last_status TEXT NOT NULL,
                    items_collected INTEGER DEFAULT 0,
                    last_error TEXT DEFAULT ''
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_failures (
                    source_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    failed_at TEXT NOT NULL,
                    error TEXT NOT NULL,
                    item_json TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 1
                )
                """
            )

            # Every collected record (all sources), deduplicated by source_id, with first/last-seen.
            # Only a budgeted subset is AI-analyzed into `opportunities`; jobs are indexed here only.
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS discovered_items (
                    source_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    item_type TEXT NOT NULL DEFAULT '',
                    canonical_url TEXT NOT NULL DEFAULT '',
                    url TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    author TEXT NOT NULL DEFAULT '',
                    published_at TEXT,
                    source_updated_at TEXT,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    evidence_json TEXT NOT NULL DEFAULT '{}',
                    supporting_json TEXT NOT NULL DEFAULT '[]',
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    seen_count INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_items_canonical ON discovered_items(canonical_url)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_items_source_type ON discovered_items(source, item_type)")

            # Additive migrations only: new columns are added in place, never by recreating tables.
            def add_columns(table: str, columns: list[tuple[str, str]]) -> None:
                existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
                for col_name, col_type in columns:
                    if col_name not in existing:
                        connection.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")

            add_columns("opportunities", [
                ("score", "REAL DEFAULT 0"),
                ("category", "TEXT DEFAULT ''"),
                ("title", "TEXT DEFAULT ''"),
                ("source", "TEXT DEFAULT ''"),
                ("status", "TEXT DEFAULT 'active'"),
                ("last_verified", "TEXT DEFAULT ''"),
                ("score_breakdown_json", "TEXT DEFAULT '{}'"),
                ("canonical_url", "TEXT DEFAULT ''"),
                ("item_type", "TEXT DEFAULT ''"),
                ("last_seen", "TEXT DEFAULT ''"),
            ])
            add_columns("source_health", [
                ("last_success_at", "TEXT DEFAULT ''"),
                ("last_duration_seconds", "REAL DEFAULT 0"),
                ("requests_ok", "INTEGER DEFAULT 0"),
                ("requests_failed", "INTEGER DEFAULT 0"),
            ])
            # Existing rows: canonical key for cross-source matching and a type for filtering.
            for row in connection.execute("SELECT source_id, url, source FROM opportunities WHERE canonical_url = '' OR item_type = ''").fetchall():
                default_type = {"GitHub": "open_source", "Hacker News": "product_tool"}.get(row["source"] or "GitHub", "")
                connection.execute(
                    "UPDATE opportunities SET canonical_url = CASE WHEN canonical_url = '' THEN ? ELSE canonical_url END, "
                    "item_type = CASE WHEN item_type = '' THEN ? ELSE item_type END WHERE source_id = ?",
                    (canonical_url(row["url"]), default_type, row["source_id"]),
                )
            # A recorded "ok" GitHub run before this migration was a successful collection.
            connection.execute("UPDATE source_health SET last_success_at = last_run_at WHERE last_success_at = '' AND last_status = 'ok'")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_opps_canonical ON opportunities(canonical_url)")

            # Backfill any records that don't have score or title yet
            rows = connection.execute(
                "SELECT source_id, report_json, date_discovered FROM opportunities WHERE title = '' OR score = 0"
            ).fetchall()
            for row in rows:
                try:
                    rep = json.loads(row["report_json"])
                    title = rep.get("title", "")
                    cat = rep.get("category", "")
                    src = rep.get("source", "GitHub")
                    last_ver = rep.get("last_verified") or row["date_discovered"]
                    
                    if "score" not in rep:
                        scored = score_opportunity(rep, rep)
                        rep["score"] = scored["score"]
                        rep["score_breakdown"] = scored["score_breakdown"]
                    
                    connection.execute(
                        """
                        UPDATE opportunities
                        SET score = ?, category = ?, title = ?, source = ?, last_verified = ?,
                            score_breakdown_json = ?, report_json = ?
                        WHERE source_id = ?
                        """,
                        (
                            rep.get("score", 0),
                            cat,
                            title,
                            src,
                            last_ver,
                            json.dumps(rep.get("score_breakdown", {})),
                            json.dumps(rep, ensure_ascii=False),
                            row["source_id"],
                        ),
                    )
                except Exception:
                    pass

            connection.commit()

    def contains(self, source_id: str, url: str, canonical: str | None = None) -> bool:
        key = canonical or canonical_url(url)
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT 1 FROM opportunities WHERE source_id = ? OR url = ? OR (? != '' AND canonical_url = ?) LIMIT 1",
                (source_id, url.rstrip("/"), key, key),
            ).fetchone()
        return row is not None

    def get_opportunity(self, source_id: str | None = None, url: str | None = None) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            if source_id:
                row = connection.execute("SELECT report_json FROM opportunities WHERE source_id = ?", (source_id,)).fetchone()
            elif url:
                row = connection.execute("SELECT report_json FROM opportunities WHERE url = ?", (url.rstrip("/"),)).fetchone()
            else:
                return None
        if not row:
            return None
        return json.loads(row["report_json"])

    def has_meaningful_update(self, source_id: str, new_item: dict[str, Any]) -> tuple[bool, str]:
        """
        Determines if an existing item has significant new evidence/changes:
        e.g., star count increased by >= 10% or >= 5, or new push/release.
        """
        existing = self.get_opportunity(source_id=source_id)
        if not existing:
            return False, "Not in store"

        from opportunity_radar.scoring import _extract_evidence_dict
        old_ev = _extract_evidence_dict(existing)
        new_ev = _extract_evidence_dict(new_item)

        # Check stars change
        old_stars = int(existing.get("github_stars") or old_ev.get("stars") or 0)
        new_stars = int(new_item.get("github_stars") or new_ev.get("stars") or 0)
        if new_stars > old_stars and (new_stars - old_stars >= 5 or (old_stars > 0 and (new_stars - old_stars) / old_stars >= 0.10)):
            return True, f"Stars increased from {old_stars} to {new_stars}"

        # Check comments / points for HN
        old_pts = int(old_ev.get("points") or 0)
        new_pts = int(new_ev.get("points") or 0)
        if new_pts > old_pts and (new_pts - old_pts >= 10):
            return True, f"Discussion points increased from {old_pts} to {new_pts}"

        # Hugging Face likes
        old_likes = int(old_ev.get("likes") or 0)
        new_likes = int(new_ev.get("likes") or 0)
        if new_likes > old_likes and (new_likes - old_likes >= 10 or (old_likes > 0 and (new_likes - old_likes) / old_likes >= 0.10)):
            return True, f"Likes increased from {old_likes} to {new_likes}"

        # Check source update date
        old_pushed = existing.get("pushed_at") or existing.get("updated_at")
        new_pushed = new_item.get("pushed_at") or new_item.get("updated_at")
        if old_pushed and new_pushed and new_pushed > old_pushed:
            return True, f"New source activity recorded at {new_pushed}"

        return False, "No significant changes"

    def save(self, source_id: str, report: dict[str, Any]) -> None:
        self.save_or_update(source_id, report, is_update=False)

    def save_or_update(self, source_id: str, report: dict[str, Any], is_update: bool = False) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        if "score" not in report:
            scored = score_opportunity(report, report)
            report["score"] = scored["score"]
            report["score_breakdown"] = scored["score_breakdown"]

        report["last_verified"] = now_iso
        previous = self.get_opportunity(source_id=source_id) or self.get_opportunity(url=report.get("url", ""))
        if previous:
            # Re-analysis keeps history: first discovery date and every supporting source seen so far.
            report["date_discovered"] = previous.get("date_discovered") or report.get("date_discovered")
            merged = list(previous.get("supporting_sources") or [])
            for entry in report.get("supporting_sources") or []:
                if all(s.get("source_id") != entry.get("source_id") for s in merged):
                    merged.append(entry)
            if merged:
                report["supporting_sources"] = merged
        if "date_discovered" not in report:
            report["date_discovered"] = now_iso

        score = float(report.get("score", 0))
        category = str(report.get("category", ""))
        title = str(report.get("title", ""))
        source = str(report.get("source", "GitHub"))
        item_type = str(report.get("item_type", ""))
        stored_url = report.get("url", "").rstrip("/")
        match_key = canonical_url(stored_url)
        score_bd_json = json.dumps(report.get("score_breakdown", {}))
        report_json = json.dumps(report, ensure_ascii=False)

        with closing(self._connect()) as connection:
            if is_update or self.contains(source_id, stored_url):
                connection.execute(
                    """
                    UPDATE opportunities
                    SET score = ?, category = ?, title = ?, source = ?, last_verified = ?,
                        score_breakdown_json = ?, report_json = ?, last_seen = ?,
                        item_type = CASE WHEN ? != '' THEN ? ELSE item_type END
                    WHERE source_id = ? OR url = ?
                    """,
                    (score, category, title, source, now_iso, score_bd_json, report_json, now_iso, item_type, item_type, source_id, stored_url),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO opportunities(
                        source_id, url, date_discovered, report_json,
                        score, category, title, source, status, last_verified, score_breakdown_json,
                        canonical_url, item_type, last_seen
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        stored_url,
                        report["date_discovered"],
                        report_json,
                        score,
                        category,
                        title,
                        source,
                        now_iso,
                        score_bd_json,
                        match_key,
                        item_type,
                        now_iso,
                    ),
                )
            connection.commit()

    def list_reports(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT report_json FROM opportunities ORDER BY score DESC, date_discovered DESC, source_id"
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def list_opportunities(
        self,
        category: str | None = None,
        source: str | None = None,
        min_score: float | None = None,
        search: str | None = None,
        sort_by: str = "score",
        limit: int = 100,
        offset: int = 0,
        item_type: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = ["status = 'active'"]
        params: list[Any] = []

        if item_type:
            conditions.append("item_type = ?")
            params.append(item_type)
        if category:
            conditions.append("category = ?")
            params.append(category)
        if source:
            conditions.append("source = ?")
            params.append(source)
        if min_score is not None:
            conditions.append("score >= ?")
            params.append(float(min_score))
        if search:
            conditions.append("(title LIKE ? OR category LIKE ? OR report_json LIKE ?)")
            term = f"%{search.strip()}%"
            params.extend([term, term, term])

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        order_by = "score DESC, last_verified DESC"
        if sort_by == "newest":
            order_by = "date_discovered DESC, score DESC"
        elif sort_by == "verified":
            order_by = "last_verified DESC, score DESC"
        elif sort_by == "title":
            order_by = "title ASC"

        query = f"SELECT report_json, item_type, last_seen FROM opportunities {where_clause} ORDER BY {order_by} LIMIT ? OFFSET ?"
        params.extend([max(1, limit), max(0, offset)])

        with closing(self._connect()) as connection:
            rows = connection.execute(query, params).fetchall()

        # Migrated rows carry item_type/last_seen only in their columns; expose them without rewriting reports.
        return [
            {**json.loads(row["report_json"]), **({"item_type": row["item_type"]} if row["item_type"] else {}),
             **({"last_seen": row["last_seen"]} if row["last_seen"] else {})}
            for row in rows
        ]

    def record_run(self, run_summary: dict[str, Any]) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO runs(
                    run_id, started_at, stopped_at, status, collected, stored, updated, failed, summary_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_summary["run_id"],
                    run_summary["started_at"],
                    run_summary["stopped_at"],
                    run_summary["status"],
                    int(run_summary.get("collected", 0)),
                    int(run_summary.get("stored", 0)),
                    int(run_summary.get("updated", 0)),
                    int(run_summary.get("failed", 0)),
                    json.dumps(run_summary, ensure_ascii=False),
                ),
            )
            connection.commit()

    def record_analysis_failure(self, item: dict[str, Any], error: str) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO analysis_failures(source_id, url, title, failed_at, error, item_json, attempts)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(source_id) DO UPDATE SET
                    url = excluded.url, title = excluded.title, failed_at = excluded.failed_at,
                    error = excluded.error, item_json = excluded.item_json, attempts = analysis_failures.attempts + 1
                """,
                (
                    str(item.get("source_id", "")),
                    str(item.get("url", "")).rstrip("/"),
                    str(item.get("title", "")),
                    now_iso,
                    error,
                    json.dumps(item, ensure_ascii=False),
                ),
            )
            connection.commit()

    def clear_analysis_failure(self, source_id: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM analysis_failures WHERE source_id = ?", (source_id,))
            connection.commit()

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT summary_json FROM runs ORDER BY started_at DESC LIMIT ?",
                (max(1, limit),),
            ).fetchall()
        return [json.loads(row["summary_json"]) for row in rows]

    def update_source_health(
        self,
        source_name: str,
        last_status: str,
        items_collected: int,
        last_error: str = "",
        duration_seconds: float = 0.0,
        requests_ok: int = 0,
        requests_failed: int = 0,
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        success_at = now_iso if last_status in {"ok", "degraded"} else ""
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO source_health(source_name, last_run_at, last_status, items_collected, last_error,
                                          last_success_at, last_duration_seconds, requests_ok, requests_failed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_name) DO UPDATE SET
                    last_run_at = excluded.last_run_at,
                    last_status = excluded.last_status,
                    items_collected = excluded.items_collected,
                    last_error = excluded.last_error,
                    last_success_at = CASE WHEN excluded.last_success_at != '' THEN excluded.last_success_at ELSE source_health.last_success_at END,
                    last_duration_seconds = excluded.last_duration_seconds,
                    requests_ok = excluded.requests_ok,
                    requests_failed = excluded.requests_failed
                """,
                (source_name, now_iso, last_status, items_collected, last_error, success_at, duration_seconds, requests_ok, requests_failed),
            )
            connection.commit()

    def get_source_health(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT h.source_name, h.last_run_at, h.last_status, h.items_collected, h.last_error,
                       h.last_success_at, h.last_duration_seconds, h.requests_ok, h.requests_failed,
                       (SELECT COUNT(*) FROM discovered_items d WHERE d.source = h.source_name) AS indexed_items,
                       (SELECT COUNT(*) FROM opportunities o WHERE o.source = h.source_name AND o.status = 'active') AS opportunities
                FROM source_health h
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_discovered(self, items: list[dict[str, Any]], seen_at: str) -> dict[str, int]:
        """Indexes every collected record (including supporting duplicates) with first/last-seen."""
        new = seen = 0
        with closing(self._connect()) as connection:
            for item in items:
                evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
                cursor = connection.execute(
                    """
                    INSERT INTO discovered_items(source_id, source, item_type, canonical_url, url, title, description, author,
                        published_at, source_updated_at, tags_json, evidence_json, supporting_json, first_seen, last_seen, seen_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(source_id) DO UPDATE SET
                        title = excluded.title, description = excluded.description, url = excluded.url,
                        canonical_url = excluded.canonical_url, item_type = excluded.item_type,
                        source_updated_at = excluded.source_updated_at, tags_json = excluded.tags_json,
                        evidence_json = excluded.evidence_json,
                        supporting_json = CASE WHEN excluded.supporting_json != '[]' THEN excluded.supporting_json ELSE discovered_items.supporting_json END,
                        last_seen = excluded.last_seen, seen_count = discovered_items.seen_count + 1
                    RETURNING seen_count
                    """,
                    (
                        str(item.get("source_id", "")),
                        str(item.get("source", "")),
                        str(item.get("item_type", "")),
                        item.get("canonical_url") or canonical_url(item.get("url")),
                        str(item.get("url", "")),
                        str(item.get("title", ""))[:300],
                        str(item.get("raw_description", ""))[:2000],
                        str(item.get("author", ""))[:120],
                        item.get("published_at") or item.get("created_at"),
                        item.get("updated_at"),
                        json.dumps([str(t) for t in item.get("topics") or []][:20], ensure_ascii=False),
                        json.dumps(evidence, ensure_ascii=False),
                        json.dumps(item.get("supporting_sources") or [], ensure_ascii=False),
                        seen_at,
                        seen_at,
                    ),
                )
                if cursor.fetchone()[0] == 1:
                    new += 1
                else:
                    seen += 1
            connection.commit()
        return {"new": new, "seen_again": seen}

    def touch_opportunities(self, items: list[dict[str, Any]], seen_at: str) -> int:
        """For records matching an existing opportunity: bump last_seen and keep every supporting source.
        Scores and the AI report are left untouched."""
        touched = 0
        with closing(self._connect()) as connection:
            for item in items:
                key = item.get("canonical_url") or canonical_url(item.get("url"))
                row = connection.execute(
                    "SELECT source_id, report_json FROM opportunities WHERE source_id = ? OR (? != '' AND canonical_url = ?) LIMIT 1",
                    (item.get("source_id", ""), key, key),
                ).fetchone()
                if row is None:
                    continue
                report = json.loads(row["report_json"])
                supporting = list(report.get("supporting_sources") or [])
                candidates = [{"source": item.get("source"), "source_id": item.get("source_id"), "url": item.get("url"), "match": "canonical_url"},
                              *(item.get("supporting_sources") or [])]
                changed = False
                for entry in candidates:
                    if entry["source_id"] != row["source_id"] and all(s.get("source_id") != entry["source_id"] for s in supporting):
                        supporting.append({**entry, "first_seen": seen_at})
                        changed = True
                if changed:
                    report["supporting_sources"] = supporting
                    connection.execute("UPDATE opportunities SET report_json = ?, last_seen = ? WHERE source_id = ?",
                                       (json.dumps(report, ensure_ascii=False), seen_at, row["source_id"]))
                else:
                    connection.execute("UPDATE opportunities SET last_seen = ? WHERE source_id = ?", (seen_at, row["source_id"]))
                touched += 1
            connection.commit()
        return touched

    def list_items(
        self,
        item_type: str | None = None,
        source: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        conditions, params = [], []
        if item_type:
            conditions.append("item_type = ?")
            params.append(item_type)
        if source:
            conditions.append("source = ?")
            params.append(source)
        if search:
            conditions.append("(title LIKE ? OR description LIKE ?)")
            params.extend([f"%{search.strip()}%"] * 2)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""SELECT source_id, source, item_type, url, title, description, author, published_at, source_updated_at,
                           tags_json, evidence_json, supporting_json, first_seen, last_seen, seen_count,
                           EXISTS(SELECT 1 FROM opportunities o WHERE o.source_id = d.source_id
                                  OR (d.canonical_url != '' AND o.canonical_url = d.canonical_url)) AS analyzed
                    FROM discovered_items d {where}
                    ORDER BY COALESCE(published_at, first_seen) DESC LIMIT ? OFFSET ?""",
                [*params, max(1, min(limit, 500)), max(0, offset)],
            ).fetchall()
        out = []
        for row in rows:
            record = dict(row)
            for column in ("tags_json", "evidence_json", "supporting_json"):
                record[column.removesuffix("_json")] = json.loads(record.pop(column))
            record["analyzed"] = bool(record["analyzed"])
            out.append(record)
        return out

    def count_items(self) -> dict[str, dict[str, int]]:
        with closing(self._connect()) as connection:
            by_type = connection.execute("SELECT item_type, COUNT(*) FROM discovered_items GROUP BY item_type").fetchall()
            opp_types = connection.execute("SELECT item_type, COUNT(*) FROM opportunities WHERE status = 'active' GROUP BY item_type").fetchall()
        return {"items_by_type": {r[0] or "unknown": r[1] for r in by_type}, "opportunities_by_type": {r[0] or "unknown": r[1] for r in opp_types}}
