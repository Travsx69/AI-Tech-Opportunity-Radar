"""Free discovery sources beyond GitHub/HN, plus the helpers every adapter shares.

Each adapter returns normalized items with the same shape as normalize_github_item, plus
`item_type`, `canonical_url`, `author`, and `published_at`. Adapters raise SourceError; the
pipeline isolates each source so one failure never stops the others.
"""
from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

USER_AGENT = "ai-tech-opportunity-radar/0.3 (+local research tool)"
ITEM_TYPES = ("product_tool", "open_source", "model_dataset", "research_release", "business", "job")


class SourceError(RuntimeError):
    """A source request failed; the message is safe to store and display."""


# ---- shared helpers ---------------------------------------------------------------------------

_SECRET_ENV = ("GITHUB_TOKEN", "GH_TOKEN", "OPENROUTER_API_KEY", "HF_TOKEN", "N8N_API_KEY", "RADAR_CONNECTOR_TOKEN")
_SECRET_PATTERNS = (
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"), "Bearer [redacted]"),
    (re.compile(r"(?i)((?:api[_-]?key|token|access_token|secret|password)=)[^&\s'\"]+"), r"\1[redacted]"),
    (re.compile(r"\b(?:ghp|gho|ghs|github_pat|hf|sk-or-v1|sk)[_-][A-Za-z0-9_\-]{16,}"), "[redacted]"),
    (re.compile(r"(?i)[A-Z]:\\(?:Users|AI-[^\\\s]*|ProgramData)[^\s'\"]*"), "[local path]"),
)


def redact(text: Any) -> str:
    """Removes credentials and local filesystem paths from error text before it is stored or served."""
    out = str(text or "")
    for name in _SECRET_ENV:
        value = (os.getenv(name) or "").strip()
        if len(value) >= 8:
            out = out.replace(value, "[redacted]")
    for pattern, repl in _SECRET_PATTERNS:
        out = pattern.sub(repl, out)
    return out[:500]


_TRACKING = re.compile(r"^(utm_|ref$|ref_src$|fbclid$|gclid$|mc_|source$)")


def canonical_url(url: str | None) -> str:
    """Stable URL key for cross-source dedup: https, no www, no fragment/tracking params, no trailing slash."""
    if not url:
        return ""
    parts = urlsplit(str(url).strip())
    host = (parts.hostname or "").lower().removeprefix("www.")
    if not host:
        return str(url).strip().rstrip("/").lower()
    path = re.sub(r"/{2,}", "/", parts.path).rstrip("/")
    if host in {"github.com", "huggingface.co"}:
        path = path.lower()  # both hosts treat owner/repo paths case-insensitively
        segments = path.split("/")
        if host == "github.com" and len(segments) > 3 and segments[3] in {"tree", "blob"}:
            path = "/".join(segments[:3])  # code deep links point at the repo; releases/issues stay distinct
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if not _TRACKING.match(k.lower())))
    return urlunsplit(("https", host, path, query, ""))


def fetch(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = 20,
    retries: int = 2,
    sleep: Callable[[float], None] = time.sleep,
    opener: Callable[..., Any] = urlopen,
) -> tuple[bytes, dict[str, str]]:
    """GET with a timeout and exponential backoff on 429/5xx/network errors. Never retries other 4xx."""
    request = Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    host = urlsplit(url).hostname or "source"
    for attempt in range(retries + 1):
        try:
            with opener(request, timeout=timeout) as response:
                return response.read(), {k.lower(): v for k, v in dict(response.headers).items()}
        except HTTPError as exc:
            retryable = exc.code == 429 or exc.code >= 500
            if not retryable or attempt == retries:
                remaining = exc.headers.get("X-RateLimit-Remaining") if exc.headers else None
                suffix = f"; rate-limit remaining: {remaining}" if remaining is not None else ""
                raise SourceError(f"{host} HTTP {exc.code}{suffix}") from exc
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            delay = float(retry_after) if retry_after and retry_after.isdigit() else 2.0 * (2 ** attempt)
            sleep(min(delay, 30.0))
        except (URLError, TimeoutError, OSError) as exc:
            if attempt == retries:
                reason = getattr(exc, "reason", exc)
                raise SourceError(f"{host} request failed: {redact(reason)}") from exc
            sleep(2.0 * (2 ** attempt))
    raise SourceError(f"{host} request failed")  # unreachable; keeps type checkers honest


def fetch_json(url: str, headers: dict[str, str] | None = None, **kwargs: Any) -> tuple[Any, dict[str, str]]:
    body, response_headers = fetch(url, {"Accept": "application/json", **(headers or {})}, **kwargs)
    try:
        return json.loads(body), response_headers
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SourceError(f"{urlsplit(url).hostname} returned malformed JSON") from exc


def _iso(value: Any) -> str | None:
    """Parses ISO-8601 or RFC-822 timestamps into UTC ISO strings; None when unparseable."""
    if not value:
        return None
    text = str(value).strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _older_than(iso: str | None, days: int | None, now: datetime) -> bool:
    return bool(days and iso and datetime.fromisoformat(iso) < now - timedelta(days=days))


def _plain(text: Any, limit: int = 1200) -> str:
    stripped = re.sub(r"<[^>]+>", " ", unescape(str(text or "")))
    return re.sub(r"\s+", " ", stripped).strip()[:limit]


def _item(**fields: Any) -> dict[str, Any]:
    """Common record shape shared with normalize_github_item / normalize_hn_item."""
    base = {
        "topics": [], "language": None, "archived": False, "fork": False,
        "author": "", "published_at": None, "created_at": None, "updated_at": None, "pushed_at": None,
    }
    base.update(fields)
    base["canonical_url"] = canonical_url(base.get("url"))
    return base


# ---- Hugging Face Hub ---------------------------------------------------------------------------

HF_KINDS = {"models": "model_dataset", "datasets": "model_dataset", "spaces": "product_tool"}
_LINK_NEXT = re.compile(r'<([^>]+)>;\s*rel="next"')


def collect_huggingface(
    kind: str,
    search: str,
    discovered_at: str,
    limit: int = 10,
    max_pages: int = 1,
    min_likes: int = 0,
    max_age_days: int | None = None,
    fetch_json_fn: Callable[..., tuple[Any, dict[str, str]]] = fetch_json,
) -> list[dict[str, Any]]:
    """Public Hub API listing (no token). Pagination follows the documented Link: rel="next" cursor, bounded."""
    if kind not in HF_KINDS:
        raise SourceError(f"unsupported Hugging Face kind: {kind}")
    params = {"search": search, "sort": "likes", "direction": "-1", "limit": max(1, min(limit, 100)), "full": "false"}
    url: str | None = f"https://huggingface.co/api/{kind}?{urlencode(params)}"
    now = datetime.fromisoformat(discovered_at)
    items: list[dict[str, Any]] = []
    for _ in range(max(1, max_pages)):
        if not url:
            break
        payload, headers = fetch_json_fn(url)
        if not isinstance(payload, list):
            raise SourceError(f"Hugging Face {kind} API returned non-list data")
        for raw in payload:
            repo_id = str(raw.get("id") or raw.get("modelId") or "")
            likes = int(raw.get("likes") or 0)
            updated = _iso(raw.get("lastModified")) or _iso(raw.get("createdAt"))
            if not repo_id or raw.get("private") or raw.get("disabled") or likes < min_likes or _older_than(updated, max_age_days, now):
                continue
            prefix = "" if kind == "models" else f"{kind}/"
            tags = [str(t) for t in (raw.get("tags") or []) if ":" not in str(t)][:15]
            task = raw.get("pipeline_tag") or ""
            description = _plain(raw.get("description")) or f"Hugging Face {kind[:-1]} {repo_id}" + (f" for {task}" if task else "")
            items.append(_item(
                source_id=f"hf:{kind}:{repo_id}",
                title=repo_id,
                source="Hugging Face",
                url=f"https://huggingface.co/{prefix}{repo_id}",
                date_discovered=discovered_at,
                raw_description=description,
                author=repo_id.split("/")[0] if "/" in repo_id else "",
                created_at=_iso(raw.get("createdAt")),
                updated_at=updated,
                pushed_at=updated,
                published_at=_iso(raw.get("createdAt")),
                topics=[t for t in [task, raw.get("library_name"), raw.get("sdk"), *tags] if t],
                item_type=HF_KINDS[kind],
                evidence={
                    "likes": likes,
                    "downloads": int(raw.get("downloads") or 0) if raw.get("downloads") is not None else None,
                    "task": task or None,
                    "kind": kind,
                    "query": search,
                    "source_updated_at": updated,
                },
            ))
        match = _LINK_NEXT.search(headers.get("link", ""))
        url = match.group(1) if match else None
    return items


# ---- RSS / Atom -------------------------------------------------------------------------------

_ATOM = "{http://www.w3.org/2005/Atom}"


def parse_feed(body: bytes, feed: dict[str, Any], discovered_at: str, max_items: int = 10, max_age_days: int | None = 30) -> list[dict[str, Any]]:
    """Parses RSS 2.0 or Atom. Raises SourceError on malformed XML or an unknown root element."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise SourceError(f"feed {feed['name']}: malformed XML ({exc})") from exc
    if root.tag == f"{_ATOM}feed":
        entries = root.findall(f"{_ATOM}entry")
        atom = True
    elif root.tag in {"rss", "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF"}:
        entries = root.findall(".//item") or root.findall(".//{http://purl.org/rss/1.0/}item")
        atom = False
    else:
        raise SourceError(f"feed {feed['name']}: not an RSS or Atom document")
    now = datetime.fromisoformat(discovered_at)
    items: list[dict[str, Any]] = []
    for entry in entries:
        if len(items) >= max_items:
            break
        if atom:
            title = entry.findtext(f"{_ATOM}title")
            link_el = entry.find(f"{_ATOM}link[@rel='alternate']")
            if link_el is None:  # Element truthiness is child count, so no `or` here
                link_el = entry.find(f"{_ATOM}link")
            link = link_el.get("href") if link_el is not None else None
            summary = entry.findtext(f"{_ATOM}summary") or entry.findtext(f"{_ATOM}content")
            published = _iso(entry.findtext(f"{_ATOM}published")) or _iso(entry.findtext(f"{_ATOM}updated"))
            updated = _iso(entry.findtext(f"{_ATOM}updated")) or published
            author = entry.findtext(f"{_ATOM}author/{_ATOM}name") or ""
            guid = entry.findtext(f"{_ATOM}id") or link
            categories = [c.get("term", "") for c in entry.findall(f"{_ATOM}category")]
        else:
            title = entry.findtext("title") or entry.findtext("{http://purl.org/rss/1.0/}title")
            link = entry.findtext("link") or entry.findtext("{http://purl.org/rss/1.0/}link")
            summary = entry.findtext("description") or entry.findtext("{http://purl.org/rss/1.0/}description")
            published = _iso(entry.findtext("pubDate")) or _iso(entry.findtext("{http://purl.org/dc/elements/1.1/}date"))
            updated = published
            author = entry.findtext("{http://purl.org/dc/elements/1.1/}creator") or entry.findtext("author") or ""
            guid = entry.findtext("guid") or link
            categories = [c.text or "" for c in entry.findall("category")]
        title, link = _plain(title, 300), (link or "").strip()
        if not title or not link.startswith("http") or _older_than(published, max_age_days, now):
            continue
        items.append(_item(
            source_id=f"rss:{feed['name']}:{canonical_url(guid) or guid}"[:300],
            title=title if not feed.get("title_prefix") else f"{feed['title_prefix']} {title}",
            source="RSS/Atom Feeds",
            url=link,
            date_discovered=discovered_at,
            raw_description=_plain(summary) or title,
            author=_plain(author, 120) or feed.get("publisher", ""),
            created_at=published,
            updated_at=updated,
            pushed_at=updated,
            published_at=published,
            topics=[c for c in (_plain(c, 60) for c in categories) if c][:10] + [feed.get("category", "")],
            item_type=feed.get("item_type", "research_release"),
            evidence={"feed": feed["name"], "publisher": feed.get("publisher", ""), "query": feed["name"], "source_updated_at": updated},
        ))
    return items


def collect_feed(
    feed: dict[str, Any],
    discovered_at: str,
    max_items: int = 10,
    max_age_days: int | None = 30,
    fetch_fn: Callable[..., tuple[bytes, dict[str, str]]] = fetch,
) -> list[dict[str, Any]]:
    body, _ = fetch_fn(feed["url"], {"Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.1"})
    return parse_feed(body, feed, discovered_at, max_items, max_age_days)


# ---- Remotive (jobs) ----------------------------------------------------------------------------

def collect_remotive(
    search: str,
    discovered_at: str,
    limit: int = 20,
    fetch_json_fn: Callable[..., tuple[Any, dict[str, str]]] = fetch_json,
) -> list[dict[str, Any]]:
    """Remotive public API. Terms: link back to the Remotive URL, credit Remotive, poll at most 4x/day,
    do not resubmit jobs to third-party job sites. Jobs are delayed 24h by Remotive."""
    payload, _ = fetch_json_fn(f"https://remotive.com/api/remote-jobs?{urlencode({'search': search, 'limit': max(1, min(limit, 50))})}")
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        raise SourceError("Remotive API returned no jobs list")
    items: list[dict[str, Any]] = []
    for raw in jobs[:limit]:
        url, title = str(raw.get("url") or ""), _plain(raw.get("title"), 200)
        if not url.startswith("https://remotive.com/") or not title:
            continue
        posted = _iso(raw.get("publication_date"))
        location = _plain(raw.get("candidate_required_location"), 120)
        items.append(_item(
            source_id=f"remotive:{raw.get('id')}",
            title=title,
            source="Remotive",
            url=url,
            date_discovered=discovered_at,
            raw_description=_plain(raw.get("description"), 800),
            author=_plain(raw.get("company_name"), 120),
            created_at=posted,
            updated_at=posted,
            pushed_at=posted,
            published_at=posted,
            topics=[str(t) for t in (raw.get("tags") or [])][:10] + [_plain(raw.get("category"), 60)],
            item_type="job",
            evidence={
                "employer": _plain(raw.get("company_name"), 120) or None,
                # Remotive lists remote jobs only; location is the stated candidate restriction, copied verbatim.
                "remote": True,
                "location": location or None,
                "job_type": raw.get("job_type") or None,
                "salary": _plain(raw.get("salary"), 80) or None,  # only what the listing states; never inferred
                "date_posted": posted,
                "application_url": url,
                "attribution": "Job listing via Remotive (remotive.com)",
                "query": search,
                "source_updated_at": posted,
            },
        ))
    return items
