"""Multi-source upgrade: adapters, isolation, dedup, migrations, API, and zero-cost safeguards.
All HTTP is mocked; nothing here touches the network."""
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from opportunity_radar.app import RadarConfig, configured_sources, run_once
from opportunity_radar.core import deduplicate, normalize_github_item, select_relevant
from opportunity_radar.hackernews import collect_hackernews, normalize_hn_item
from opportunity_radar.pipeline import run_discovery
from opportunity_radar.registry import DEFAULT_CONFIG_PATH, SourceSpec, build_sources, load_source_config
from opportunity_radar.service import make_server
from opportunity_radar.sources import (
    SourceError, canonical_url, collect_huggingface, collect_remotive, fetch, parse_feed, redact,
)
from opportunity_radar.store import OpportunityStore

NOW = "2026-10-16T00:00:00+00:00"
ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = {
    "category": "technology worth testing", "summary": "s", "what_it_does": "w", "why_it_matters": "y",
    "potential_use_for_us": "p", "business_opportunity": "b", "technical_opportunity": "t",
    "estimated_effort": "small", "recommended_next_action": "r", "evidence": ["e"], "confidence": "medium",
}
GH_RAW = {
    "id": 1, "full_name": "acme/agent-kit", "html_url": "https://github.com/acme/agent-kit",
    "description": "AI agent automation toolkit", "stargazers_count": 40, "forks_count": 3,
    "topics": ["ai-agents"], "pushed_at": "2026-10-10T00:00:00Z", "owner": {"login": "acme"},
}
HN_HIT = {
    "objectID": "555", "title": "Show HN: Agent kit for AI automation", "url": "https://GitHub.com/Acme/agent-kit/tree/main?utm_source=hn",
    "points": 80, "num_comments": 12, "author": "pg", "created_at": "2026-10-15T00:00:00Z",
}


def spec(name, *requests, **kw):
    return SourceSpec(name, True, requests=list(requests), **kw)


class FakeResponse:
    def __init__(self, body, headers=None):
        self.body, self.headers = body, headers or {}
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self): return self.body


class HttpTests(unittest.TestCase):
    def test_fetch_backs_off_on_429_then_succeeds(self):
        calls, sleeps = [], []
        def opener(request, timeout):
            calls.append(timeout)
            if len(calls) == 1:
                raise HTTPError(request.full_url, 429, "slow down", {"Retry-After": "3"}, BytesIO(b""))
            return FakeResponse(b"ok", {"Content-Type": "text/plain"})
        body, headers = fetch("https://example.com/x", timeout=7, opener=opener, sleep=sleeps.append)
        self.assertEqual(body, b"ok")
        self.assertEqual(sleeps, [3.0])
        self.assertEqual(calls, [7, 7])

    def test_fetch_uses_exponential_backoff_on_5xx_and_gives_up(self):
        sleeps = []
        def opener(request, timeout):
            raise HTTPError(request.full_url, 503, "down", {}, BytesIO(b""))
        with self.assertRaisesRegex(SourceError, "HTTP 503"):
            fetch("https://example.com/x", retries=2, opener=opener, sleep=sleeps.append)
        self.assertEqual(sleeps, [2.0, 4.0])

    def test_fetch_does_not_retry_client_errors_and_reports_rate_limit(self):
        sleeps = []
        def opener(request, timeout):
            raise HTTPError(request.full_url, 403, "forbidden", {"X-RateLimit-Remaining": "0"}, BytesIO(b""))
        with self.assertRaisesRegex(SourceError, "HTTP 403; rate-limit remaining: 0"):
            fetch("https://api.github.com/search", opener=opener, sleep=sleeps.append)
        self.assertEqual(sleeps, [])

    def test_fetch_timeout_becomes_source_error(self):
        def opener(request, timeout):
            raise URLError(TimeoutError("timed out"))
        with self.assertRaisesRegex(SourceError, "request failed"):
            fetch("https://example.com/x", retries=1, opener=opener, sleep=lambda s: None)

    def test_canonical_url_normalizes_for_cross_source_matching(self):
        self.assertEqual(canonical_url("http://www.GitHub.com/Acme/Agent-Kit/tree/main/"), "https://github.com/acme/agent-kit")
        self.assertEqual(canonical_url("https://example.com/post/?utm_source=x&id=2#top"), "https://example.com/post?id=2")
        self.assertEqual(canonical_url(""), "")

    def test_github_release_and_issue_urls_stay_distinct(self):
        # live check regression: all n8n release entries collapsed into one record
        a = canonical_url("https://github.com/n8n-io/n8n/releases/tag/n8n@2.1.0")
        b = canonical_url("https://github.com/n8n-io/n8n/releases/tag/n8n@2.2.0")
        self.assertNotEqual(a, b)
        self.assertNotEqual(canonical_url("https://github.com/a/b/issues/1"), "https://github.com/a/b")


class GitHubTests(unittest.TestCase):
    def test_github_normalization_adds_type_canonical_and_author(self):
        item = normalize_github_item(GH_RAW, NOW, "ai agents")
        self.assertEqual(item["item_type"], "open_source")
        self.assertEqual(item["canonical_url"], "https://github.com/acme/agent-kit")
        self.assertEqual(item["author"], "acme")
        self.assertEqual(item["url"], GH_RAW["html_url"])  # display URL unchanged (existing records match on it)

    def test_relevance_uses_word_boundaries(self):
        # "ai" inside "maintain"/"email" used to count as a match
        unrelated = {"title": "x/mailer", "raw_description": "Maintain email campaigns", "topics": [], "evidence": {"stars": 900}}
        self.assertEqual(select_relevant([unrelated], limit=5), [])


class HuggingFaceTests(unittest.TestCase):
    def test_parses_models_and_follows_bounded_link_pagination(self):
        pages = {
            "first": ([
                {"id": "org/agent-7b", "likes": 50, "downloads": 1200, "pipeline_tag": "text-generation", "tags": ["agent", "license:mit"], "createdAt": "2026-09-01T00:00:00.000Z", "lastModified": "2026-10-01T00:00:00.000Z"},
                {"id": "org/private", "likes": 99, "private": True},
                {"id": "org/unpopular", "likes": 1},
            ], {"link": '<https://huggingface.co/api/models?cursor=abc>; rel="next"'}),
            "https://huggingface.co/api/models?cursor=abc": ([{"id": "org/second-page", "likes": 20}], {"link": '<https://huggingface.co/api/models?cursor=def>; rel="next"'}),
        }
        requested = []
        def fake(url):
            requested.append(url)
            return pages.get(url) or pages["first"]
        items = collect_huggingface("models", "agent", NOW, limit=3, max_pages=2, min_likes=10, fetch_json_fn=fake)
        self.assertEqual([i["title"] for i in items], ["org/agent-7b", "org/second-page"])
        self.assertEqual(len(requested), 2)  # stops at max_pages even though a third page exists
        self.assertIn("limit=3", requested[0])
        first = items[0]
        self.assertEqual(first["source_id"], "hf:models:org/agent-7b")
        self.assertEqual(first["url"], "https://huggingface.co/org/agent-7b")
        self.assertEqual(first["item_type"], "model_dataset")
        self.assertEqual(first["evidence"]["likes"], 50)
        self.assertEqual(first["evidence"]["downloads"], 1200)
        self.assertNotIn("license:mit", first["topics"])

    def test_spaces_get_prefixed_urls_and_tool_type(self):
        items = collect_huggingface("spaces", "agent", NOW, fetch_json_fn=lambda url: ([{"id": "a/b", "likes": 5, "sdk": "gradio"}], {}))
        self.assertEqual(items[0]["url"], "https://huggingface.co/spaces/a/b")
        self.assertEqual(items[0]["item_type"], "product_tool")
        self.assertIsNone(items[0]["evidence"]["downloads"])  # not reported -> None, not invented 0

    def test_non_list_payload_raises(self):
        with self.assertRaises(SourceError):
            collect_huggingface("models", "x", NOW, fetch_json_fn=lambda url: ({"error": "bad"}, {}))


class HackerNewsTests(unittest.TestCase):
    def test_algolia_query_includes_points_filter_and_parses_hits(self):
        captured = {}
        def fake(url, headers):
            captured["url"] = url
            return {"hits": [HN_HIT]}
        hits = collect_hackernews("AI agent", 10, request_json=fake, min_points=5)
        self.assertEqual(len(hits), 1)
        self.assertIn("numericFilters=points%3E%3D5", captured["url"])

    def test_hn_types_reflect_post_kind(self):
        self.assertEqual(normalize_hn_item(HN_HIT, NOW, "q")["item_type"], "open_source")  # links a GitHub repo
        ask = normalize_hn_item({**HN_HIT, "title": "Ask HN: what tool do you need?", "url": None}, NOW, "q")
        self.assertEqual(ask["item_type"], "business")
        show = normalize_hn_item({**HN_HIT, "url": "https://example.com"}, NOW, "q")
        self.assertEqual(show["item_type"], "product_tool")
        news = normalize_hn_item({**HN_HIT, "title": "Companies rushed in on AI", "url": "https://news.example/x"}, NOW, "q")
        self.assertEqual(news["item_type"], "business")


RSS = b"""<?xml version="1.0"?><rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><title>T</title>
<item><title>New agent SDK</title><link>https://example.com/sdk</link><description>&lt;p&gt;An &lt;b&gt;agent&lt;/b&gt; SDK&lt;/p&gt;</description>
<pubDate>Wed, 15 Oct 2026 10:00:00 GMT</pubDate><guid>sdk-1</guid><dc:creator>Jane</dc:creator><category>AI</category></item>
<item><title>Old post</title><link>https://example.com/old</link><pubDate>Mon, 01 Jan 2024 10:00:00 GMT</pubDate></item>
<item><title>No link</title></item>
</channel></rss>"""
ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Releases</title>
<entry><id>tag:github.com,2008:v1</id><title>v1.2.0</title><link rel="alternate" href="https://github.com/acme/x/releases/tag/v1.2.0"/>
<updated>2026-10-14T00:00:00Z</updated><content type="html">Fixes</content><author><name>bot</name></author></entry></feed>"""


class FeedTests(unittest.TestCase):
    feed = {"name": "test", "publisher": "Example", "item_type": "research_release", "category": "ai"}

    def test_rss_parsing_strips_html_and_filters_old_or_linkless(self):
        items = parse_feed(RSS, self.feed, NOW, max_items=10, max_age_days=30)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["title"], "New agent SDK")
        self.assertEqual(item["raw_description"], "An agent SDK")
        self.assertEqual(item["author"], "Jane")
        self.assertEqual(item["published_at"], "2026-10-15T10:00:00+00:00")
        self.assertEqual(item["source"], "RSS/Atom Feeds")
        self.assertEqual(item["evidence"]["publisher"], "Example")

    def test_atom_parsing_with_title_prefix(self):
        items = parse_feed(ATOM, {**self.feed, "title_prefix": "X release", "item_type": "open_source"}, NOW)
        self.assertEqual(items[0]["title"], "X release v1.2.0")
        self.assertEqual(items[0]["url"], "https://github.com/acme/x/releases/tag/v1.2.0")
        self.assertEqual(items[0]["item_type"], "open_source")

    def test_malformed_and_non_feed_documents_raise(self):
        with self.assertRaisesRegex(SourceError, "malformed XML"):
            parse_feed(b"<rss><channel><item>", self.feed, NOW)
        with self.assertRaisesRegex(SourceError, "not an RSS or Atom"):
            parse_feed(b"<html><body>hi</body></html>", self.feed, NOW)

    def test_max_items_bound(self):
        many = b"<rss><channel>" + b"".join(f"<item><title>Post {i}</title><link>https://e.com/{i}</link></item>".encode() for i in range(30)) + b"</channel></rss>"
        self.assertEqual(len(parse_feed(many, self.feed, NOW, max_items=5, max_age_days=None)), 5)


class RemotiveTests(unittest.TestCase):
    def test_job_fields_are_copied_not_invented(self):
        payload = {"jobs": [
            {"id": 9, "url": "https://remotive.com/remote-jobs/software-dev/ai-engineer-9", "title": "AI Automation Engineer",
             "company_name": "Acme", "candidate_required_location": "USA", "publication_date": "2026-10-12T08:00:00",
             "job_type": "full_time", "salary": "", "tags": ["n8n"], "category": "Software Development", "description": "<p>Build agents</p>"},
            {"id": 10, "url": "https://evil.example/job", "title": "Phish"},
        ]}
        items = collect_remotive("AI", NOW, fetch_json_fn=lambda url: (payload, {}))
        self.assertEqual(len(items), 1)
        ev = items[0]["evidence"]
        self.assertEqual(ev["employer"], "Acme")
        self.assertEqual(ev["location"], "USA")
        self.assertIsNone(ev["salary"])  # empty in the listing -> None, never guessed
        self.assertEqual(ev["date_posted"], "2026-10-12T08:00:00+00:00")
        self.assertEqual(ev["application_url"], payload["jobs"][0]["url"])
        self.assertIn("Remotive", ev["attribution"])
        self.assertEqual(items[0]["item_type"], "job")

    def test_irrelevant_jobs_are_filtered_and_jobs_skip_ai(self):
        jobs = [{"id": 1, "url": "https://remotive.com/a", "title": "Remote Office Assistant", "tags": []},
                {"id": 3, "url": "https://remotive.com/c", "title": "Tier III Service Desk Engineer", "tags": ["support"]},
                {"id": 4, "url": "https://remotive.com/d", "title": "Senior React Full-stack Developer", "tags": ["react"]},
                {"id": 5, "url": "https://remotive.com/e", "title": "Content Reviewer - United States", "tags": ["AI/ML", "api"]},
                {"id": 6, "url": "https://remotive.com/f", "title": "Senior AI Engineer", "tags": []},
                {"id": 2, "url": "https://remotive.com/b", "title": "Workflow Automation Specialist", "tags": []}]
        specs = build_sources({"remotive": {"enabled": True, "searches": ["automation"]}}, NOW, [], 5,
                              remotive_collect=lambda s, d, n: collect_remotive(s, d, n, fetch_json_fn=lambda u: ({"jobs": jobs}, {})))
        remotive = next(s for s in specs if s.name == "Remotive")
        items = remotive.requests[0][1]()
        self.assertEqual([i["title"] for i in items], ["Senior AI Engineer", "Workflow Automation Specialist"])
        self.assertEqual(select_relevant(items, limit=5), [])

    def test_malformed_payload_raises(self):
        with self.assertRaises(SourceError):
            collect_remotive("AI", NOW, fetch_json_fn=lambda url: ([], {}))


class PipelineIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = OpportunityStore(Path(self.tmp.name) / "radar.db")
        self.calls = []
        self.generate = lambda prompt: self.calls.append(prompt) or json.dumps(ANALYSIS)

    def tearDown(self):
        self.tmp.cleanup()

    def test_one_failing_source_does_not_stop_others_and_run_is_partial(self):
        def boom():
            raise SourceError("feed down")
        sources = [
            spec("GitHub", ("github:q", lambda: [normalize_github_item(GH_RAW, NOW, "q")])),
            spec("RSS/Atom Feeds", ("rss:a", boom), ("rss:b", lambda: [])),
            spec("Hugging Face", ("hf:x", boom)),
        ]
        result = run_discovery(sources, self.store, self.generate, NOW, max_analyzed=5)
        self.assertEqual(result["status"], "partial_failure")
        self.assertEqual(result["stored"], 1)
        self.assertEqual(result["sources"]["RSS/Atom Feeds"]["status"], "degraded")
        self.assertEqual(result["sources"]["Hugging Face"]["status"], "failed")
        health = {h["source_name"]: h for h in self.store.get_source_health()}
        self.assertEqual(health["GitHub"]["last_status"], "ok")
        self.assertTrue(health["GitHub"]["last_success_at"])
        self.assertEqual(health["Hugging Face"]["last_success_at"], "")
        self.assertEqual(health["Hugging Face"]["last_error"], "feed down")
        self.assertEqual(health["GitHub"]["indexed_items"], 1)

    def test_all_sources_failing_is_a_failed_run_not_success(self):
        def boom():
            raise RuntimeError("down")
        result = run_discovery([spec("GitHub", ("q", boom))], self.store, self.generate, NOW)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.calls, [])

    def test_unexpected_exception_types_are_isolated(self):
        def bad():
            raise KeyError("missing")
        result = run_discovery([spec("A", ("a", bad)), spec("B", ("b", lambda: []))], self.store, self.generate, NOW)
        self.assertEqual(result["sources"]["B"]["status"], "ok")

    def test_min_interval_skips_recently_polled_source(self):
        self.store.update_source_health("Remotive", "ok", 3)
        hit = []
        result = run_discovery([spec("Remotive", ("r", lambda: hit.append(1) or []), min_interval_minutes=360)], self.store, self.generate, NOW)
        self.assertEqual(hit, [])
        self.assertEqual(result["sources"]["Remotive"]["status"], "skipped")
        self.assertEqual(result["status"], "success")

    def test_request_gap_is_applied_between_requests(self):
        sleeps = []
        run_discovery([spec("Remotive", ("a", lambda: []), ("b", lambda: []), request_gap_seconds=35)], self.store, self.generate, NOW, sleep=sleeps.append)
        self.assertEqual(sleeps, [35])

    def test_ai_calls_never_exceed_max_analyzed_with_many_sources(self):
        def many(prefix, n):
            return lambda: [normalize_github_item({**GH_RAW, "id": f"{prefix}{i}", "full_name": f"{prefix}/agent-{i}", "html_url": f"https://github.com/{prefix}/agent-{i}"}, NOW, "q") for i in range(n)]
        sources = [spec(f"S{k}", (f"s{k}", many(f"o{k}", 10))) for k in range(5)]
        run_discovery(sources, self.store, self.generate, NOW, max_analyzed=3)
        self.assertEqual(len(self.calls), 3)

    def test_each_source_gets_a_fair_slot_within_the_budget(self):
        gh = lambda: [normalize_github_item({**GH_RAW, "id": i, "full_name": f"a/agent-{i}", "html_url": f"https://github.com/a/agent-{i}", "stargazers_count": 400}, NOW, "q") for i in range(5)]
        hn = lambda: [normalize_hn_item({**HN_HIT, "objectID": "9", "url": "https://example.com/agent", "points": 6}, NOW, "AI agent")]
        result = run_discovery([spec("GitHub", ("g", gh)), spec("Hacker News", ("h", hn))], self.store, self.generate, NOW, max_analyzed=2)
        self.assertEqual(sorted(r["source"] for r in result["reports"]), ["GitHub", "Hacker News"])

    def test_errors_are_redacted_in_run_and_health(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_supersecretvalue1234567890"}):
            def leak():
                raise RuntimeError("failed with ghp_supersecretvalue1234567890 at C:\\Users\\me\\radar\\x.py")
            result = run_discovery([spec("GitHub", ("q", leak))], self.store, self.generate, NOW)
        self.assertNotIn("supersecret", json.dumps(result))
        self.assertNotIn("C:\\Users", json.dumps(result))
        self.assertNotIn("supersecret", json.dumps(self.store.get_source_health()))


class CrossSourceDedupTests(unittest.TestCase):
    def test_hn_post_linking_repo_merges_into_github_record_with_attribution(self):
        gh = normalize_github_item(GH_RAW, NOW, "q")
        hn = normalize_hn_item(HN_HIT, NOW, "AI agent")
        unique = deduplicate([hn, gh])
        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0]["source"], "GitHub")
        self.assertEqual(unique[0]["supporting_sources"][0]["source"], "Hacker News")
        self.assertEqual(unique[0]["supporting_sources"][0]["match"], "canonical_url")

    def test_near_identical_titles_across_sources_merge(self):
        a = {"source_id": "rss:x:1", "source": "RSS/Atom Feeds", "title": "OpenAI launches new agent builder platform", "url": "https://openai.com/a"}
        b = {"source_id": "hn:2", "source": "Hacker News", "title": "OpenAI launches new agent builder platform!", "url": "https://news.example/b"}
        c = {"source_id": "hn:3", "source": "Hacker News", "title": "Completely different story about agents", "url": "https://x.example/c"}
        unique = deduplicate([a, b, c])
        self.assertEqual(len(unique), 2)
        merged = next(u for u in unique if u["source_id"] == "rss:x:1")
        self.assertEqual(merged["supporting_sources"][0]["match"], "title_similarity")

    def test_existing_opportunity_gets_attribution_without_duplicate_or_rescore(self):
        with tempfile.TemporaryDirectory() as d:
            store = OpportunityStore(Path(d) / "radar.db")
            gen_calls = []
            gen = lambda p: gen_calls.append(p) or json.dumps(ANALYSIS)
            run_discovery([spec("GitHub", ("q", lambda: [normalize_github_item(GH_RAW, NOW, "q")]))], store, gen, NOW)
            before = store.list_reports()[0]
            later = "2026-10-17T00:00:00+00:00"
            hn = lambda: [normalize_hn_item(HN_HIT, later, "AI agent")]
            result = run_discovery([spec("Hacker News", ("h", hn))], store, gen, later)
            reports = store.list_reports()
            self.assertEqual(len(reports), 1)
            self.assertEqual(len(gen_calls), 1)  # no second AI call for a duplicate
            self.assertEqual(reports[0]["score"], before["score"])
            self.assertEqual(reports[0]["supporting_sources"][0]["source_id"], "hn:555")
            self.assertEqual(result["stored"], 0)
            with closing(store._connect()) as c:
                self.assertEqual(c.execute("SELECT last_seen FROM opportunities").fetchone()[0], later)
                self.assertEqual(c.execute("SELECT COUNT(*) FROM discovered_items").fetchone()[0], 2)

    def test_items_index_tracks_first_and_last_seen(self):
        with tempfile.TemporaryDirectory() as d:
            store = OpportunityStore(Path(d) / "radar.db")
            item = normalize_github_item(GH_RAW, NOW, "q")
            self.assertEqual(store.upsert_discovered([item], NOW), {"new": 1, "seen_again": 0})
            self.assertEqual(store.upsert_discovered([item], "2026-10-18T00:00:00+00:00"), {"new": 0, "seen_again": 1})
            row = store.list_items()[0]
            self.assertEqual((row["first_seen"], row["last_seen"], row["seen_count"]), (NOW, "2026-10-18T00:00:00+00:00", 2))


OLD_SCHEMA = """
CREATE TABLE opportunities (source_id TEXT PRIMARY KEY, url TEXT NOT NULL UNIQUE, date_discovered TEXT NOT NULL, report_json TEXT NOT NULL,
  score REAL DEFAULT 0, category TEXT DEFAULT '', title TEXT DEFAULT '', source TEXT DEFAULT '', status TEXT DEFAULT 'active',
  last_verified TEXT DEFAULT '', score_breakdown_json TEXT DEFAULT '{}');
CREATE TABLE runs (run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, stopped_at TEXT NOT NULL, status TEXT NOT NULL,
  collected INTEGER DEFAULT 0, stored INTEGER DEFAULT 0, updated INTEGER DEFAULT 0, failed INTEGER DEFAULT 0, summary_json TEXT NOT NULL);
CREATE TABLE source_health (source_name TEXT PRIMARY KEY, last_run_at TEXT NOT NULL, last_status TEXT NOT NULL, items_collected INTEGER DEFAULT 0, last_error TEXT DEFAULT '');
"""


class MigrationTests(unittest.TestCase):
    def test_pre_upgrade_schema_migrates_in_place_preserving_records(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "radar.db"
            with closing(sqlite3.connect(path)) as c:
                c.executescript(OLD_SCHEMA)
                report = {**ANALYSIS, "title": "acme/agent-kit", "source": "GitHub", "url": "https://github.com/Acme/agent-kit", "score": 77.7, "date_discovered": NOW}
                c.execute("INSERT INTO opportunities VALUES ('github:1','https://github.com/Acme/agent-kit',?,?,77.7,'technology worth testing','acme/agent-kit','GitHub','active',?,'{}')",
                          (NOW, json.dumps(report), NOW))
                c.execute("INSERT INTO runs VALUES ('run_1', ?, ?, 'success', 48, 1, 0, 0, '{}')", (NOW, NOW))
                c.execute("INSERT INTO source_health VALUES ('GitHub', ?, 'ok', 48, '')", (NOW,))
                c.commit()
            for _ in range(2):  # idempotent
                store = OpportunityStore(path)
            with closing(store._connect()) as c:
                row = c.execute("SELECT score, canonical_url, item_type, report_json FROM opportunities").fetchone()
                self.assertEqual(row["score"], 77.7)
                self.assertEqual(row["canonical_url"], "https://github.com/acme/agent-kit")
                self.assertEqual(row["item_type"], "open_source")
                self.assertEqual(json.loads(row["report_json"])["title"], "acme/agent-kit")
                self.assertEqual(c.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 1)
            self.assertEqual(store.get_source_health()[0]["last_success_at"], NOW)
            self.assertTrue(store.contains("github:other", "https://github.com/acme/agent-kit/"))
            self.assertEqual(store.list_opportunities(item_type="open_source")[0]["item_type"], "open_source")

    @unittest.skipUnless((ROOT / "data" / "radar.db.pre-multisource-20261016.bak").exists(), "production backup not present")
    def test_real_backup_copy_migrates_without_losing_records(self):
        with tempfile.TemporaryDirectory() as d:
            copy = Path(d) / "radar.db"
            shutil.copy(ROOT / "data" / "radar.db.pre-multisource-20261016.bak", copy)
            with closing(sqlite3.connect(copy)) as c:
                before = c.execute("SELECT source_id, score, report_json FROM opportunities ORDER BY source_id").fetchall()
                runs_before = c.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            store = OpportunityStore(copy)
            with closing(store._connect()) as c:
                after = c.execute("SELECT source_id, score, report_json FROM opportunities ORDER BY source_id").fetchall()
                self.assertEqual([tuple(r) for r in after], [tuple(r) for r in before])
                self.assertEqual(c.execute("SELECT COUNT(*) FROM runs").fetchone()[0], runs_before)
                self.assertEqual(c.execute("SELECT COUNT(*) FROM opportunities WHERE canonical_url = ''").fetchone()[0], 0)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        cfg = load_source_config()
        (root / "sources.json").write_text(json.dumps(cfg), encoding="utf-8")
        self.config = RadarConfig(data_dir=root, queries=("q",), sources_config=root / "sources.json")
        store = OpportunityStore(root / "radar.db")
        run_discovery([
            spec("GitHub", ("q", lambda: [normalize_github_item(GH_RAW, NOW, "q")])),
            spec("Remotive", ("r", lambda: collect_remotive("AI", NOW, fetch_json_fn=lambda u: ({"jobs": [
                {"id": 1, "url": "https://remotive.com/x", "title": "AI Engineer", "company_name": "Acme"}]}, {})))),
            spec("Hugging Face", ("h", lambda: (_ for _ in ()).throw(SourceError("huggingface.co HTTP 503")))),
        ], store, lambda p: json.dumps(ANALYSIS), NOW)
        self.server = make_server("127.0.0.1", 0, self.config, runner=lambda c: {})
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.tmp.cleanup()

    def get(self, path):
        with urlopen(self.base + path, timeout=5) as r:
            return json.load(r)

    def test_sources_api_distinguishes_configured_enabled_healthy_collecting(self):
        data = self.get("/api/sources")
        rows = {r["source_name"]: r for r in data["sources"]}
        for legacy in ("source_name", "last_run_at", "last_status", "items_collected", "last_error"):
            self.assertIn(legacy, rows["GitHub"])  # fields the website connector syncs
        self.assertEqual(data["summary"]["configured"], 6)
        self.assertEqual(data["summary"]["enabled"], 5)
        self.assertTrue(rows["GitHub"]["healthy"] and rows["GitHub"]["collecting"])
        self.assertEqual(rows["GitHub"]["indexed_items"], 1)
        self.assertFalse(rows["Hugging Face"]["healthy"])
        self.assertEqual(rows["Hugging Face"]["last_status"], "failed")
        self.assertEqual(rows["Hacker News"]["last_status"], "never_run")
        self.assertFalse(rows["Product Hunt"]["enabled"])
        self.assertEqual(rows["Product Hunt"]["last_status"], "disabled")
        self.assertEqual(data["summary"]["healthy"], 2)  # GitHub + Remotive
        body = json.dumps(data)
        self.assertNotIn("C:\\\\", body)
        self.assertNotIn(self.tmp.name.replace("\\", "\\\\"), body)

    def test_opportunity_api_contract_and_type_filter(self):
        data = self.get("/api/opportunities")
        self.assertEqual(set(data), {"opportunities", "count"})
        self.assertEqual(data["opportunities"][0]["item_type"], "open_source")
        self.assertEqual(self.get("/api/opportunities?type=job")["count"], 0)

    def test_items_api_lists_jobs_with_fields(self):
        data = self.get("/api/items?type=job")
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["items"][0]["evidence"]["employer"], "Acme")
        self.assertEqual(data["items_by_type"], {"job": 1, "open_source": 1})

    def test_bad_numeric_params_return_400(self):
        with self.assertRaises(HTTPError) as ctx:
            urlopen(self.base + "/api/opportunities?limit=abc", timeout=5)
        self.assertEqual(ctx.exception.code, 400)

    def test_dashboard_has_no_hardcoded_source_count_or_placeholder_health(self):
        with urlopen(self.base + "/", timeout=5) as r:
            html = r.read().decode("utf-8")
        self.assertNotIn('id="statSourcesCount">2<', html)
        self.assertNotIn("defaultSources", html)
        self.assertIn("/api/items", html)


class ZeroCostAndConfigTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_source_config(DEFAULT_CONFIG_PATH)

    def test_enabled_sources_need_no_payment_or_credentials_and_use_https(self):
        specs = build_sources(self.cfg, NOW, ["q"], 5)
        self.assertEqual({s.name for s in specs if s.enabled}, {"GitHub", "Hacker News", "Hugging Face", "RSS/Atom Feeds", "Remotive"})
        for key, section in self.cfg.items():
            if isinstance(section, dict) and section.get("enabled"):
                self.assertFalse(section.get("requires_payment"), key)
                self.assertFalse(section.get("requires_credentials"), key)
        for feed in self.cfg["rss"]["feeds"]:
            self.assertTrue(feed["url"].startswith("https://"), feed["name"])

    def test_paid_or_credentialed_sources_cannot_be_enabled_by_flag(self):
        specs = build_sources({"hugging_face": {"enabled": True, "requires_payment": True, "searches": [{"kind": "models", "search": "x"}]},
                               "product_hunt": {"enabled": True, "requires_credentials": True}}, NOW, ["q"], 5)
        by_name = {s.name: s for s in specs}
        self.assertFalse(by_name["Hugging Face"].enabled)
        self.assertIn("zero-cost", by_name["Hugging Face"].disabled_reason)
        self.assertFalse(by_name["Product Hunt"].enabled)

    def test_disabled_feeds_are_not_requested(self):
        specs = build_sources(self.cfg, NOW, ["q"], 5)
        rss = next(s for s in specs if s.name == "RSS/Atom Feeds")
        labels = [label for label, _ in rss.requests]
        self.assertNotIn("rss:deepmind-blog", labels)
        self.assertNotIn("rss:microsoft-ai-blog", labels)
        self.assertEqual(len(labels), 10)

    def test_request_volume_per_run_is_bounded(self):
        specs = build_sources(self.cfg, NOW, ["a", "b", "c", "d", "e", "f"], 8)
        total = sum(len(s.requests) for s in specs if s.enabled)
        self.assertLessEqual(total, 30)
        remotive = next(s for s in specs if s.name == "Remotive")
        self.assertGreaterEqual(remotive.min_interval_minutes, 360)  # Remotive asks for at most 4 fetches/day
        self.assertGreaterEqual(remotive.request_gap_seconds, 30)  # and blocks >2 requests/minute

    def test_building_sources_makes_no_network_calls(self):
        with patch("opportunity_radar.sources.urlopen", side_effect=AssertionError("network")):
            configured_sources(RadarConfig(sources_config=DEFAULT_CONFIG_PATH))


class OpenRouterPreservationTests(unittest.TestCase):
    def test_openrouter_settings_flow_through_unchanged(self):
        env = {"AI_PROVIDER": "openrouter", "OPENROUTER_API_KEY": "k-test", "OPENROUTER_MODEL": "vendor/model:free", "OPENROUTER_TIMEOUT": "90"}
        with patch.dict(os.environ, env, clear=True):
            config = RadarConfig.from_env()
        self.assertEqual((config.ai_provider, config.openrouter_model, config.openrouter_timeout), ("openrouter", "vendor/model:free", 90))
        with tempfile.TemporaryDirectory() as d, patch("opportunity_radar.app.OpenRouterClient") as client:
            run_once(RadarConfig(**{**config.__dict__, "data_dir": Path(d), "queries": (), "sources_config": None}), collect=lambda *_: [])
        client.assert_called_once_with("vendor/model:free", "k-test", 90)

    def test_defaults_and_example_config_are_unchanged(self):
        self.assertEqual(RadarConfig().openrouter_model, "openrouter/free")
        self.assertEqual(RadarConfig().ai_provider, "ollama")
        example = (ROOT / ".env.example").read_text(encoding="utf-8")
        for line in ("AI_PROVIDER=ollama", "OPENROUTER_MODEL=openrouter/free", "OPENROUTER_TIMEOUT=120"):
            self.assertIn(line, example)
        self.assertNotIn("openrouter", json.dumps(load_source_config()).lower())


class RedactionTests(unittest.TestCase):
    def test_redact_strips_tokens_bearer_query_secrets_and_paths(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-abcdefabcdefabcdef"}):
            text = redact("key sk-or-v1-abcdefabcdefabcdef Bearer abc.def https://x/y?api_key=zzz&a=1 C:\\Users\\alice\\file.py hf_abcdefghijklmnopqrstu")
        for secret in ("abcdefabcdef", "abc.def", "zzz", "alice", "hf_abcdefghijklmnopqrstu"):
            self.assertNotIn(secret, text)
        self.assertIn("a=1", text)


if __name__ == "__main__":
    unittest.main()
