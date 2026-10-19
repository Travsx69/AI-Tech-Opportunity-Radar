from __future__ import annotations

# Served at / by service.py. Live data from /api/opportunities, /api/items, /api/runs, /api/sources.
# Motion (https://motion.dev) animates HTML; SVG motion is CSS. Without the CDN the page still works, unanimated.
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Tech Opportunity Radar</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@112,600;112,800&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
/* Layout: instrument panel. Header + ticker, scope + readouts, then tabbed detail views. */
:root {
  --bg: #eef1f3; --panel: #ffffff; --ink: #14202b; --muted: #5d6b78; --line: #d5dce2;
  --signal: #0f8a96; --signal-soft: rgba(15, 138, 150, .12);
  --ok: #1d8a4e; --warn: #b7741a; --bad: #c0392b; --off: #8a96a1;
  --display: "Archivo", "Arial Narrow", system-ui, sans-serif;
  --body: "Instrument Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "JetBrains Mono", ui-monospace, Consolas, monospace;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #0b1117; --panel: #111a22; --ink: #e4ecf1; --muted: #8a9aa8; --line: #213040;
  --signal: #4fd1dc; --signal-soft: rgba(79, 209, 220, .12);
  --ok: #4cc283; --warn: #e2a64a; --bad: #ef6b5d; --off: #5d6c79; color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #0b1117; --panel: #111a22; --ink: #e4ecf1; --muted: #8a9aa8; --line: #213040;
  --signal: #4fd1dc; --signal-soft: rgba(79, 209, 220, .12);
  --ok: #4cc283; --warn: #e2a64a; --bad: #ef6b5d; --off: #5d6c79; color-scheme: dark; }

* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.5 var(--body);
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); padding-block: 20px 48px; }
[hidden] { display: none !important; }
.wrap { max-width: 1180px; margin: 0 auto; display: grid; gap: 20px; }
a { color: inherit; }
a:focus-visible, button:focus-visible, select:focus-visible, input:focus-visible, .blip:focus-visible { outline: 2px solid var(--signal); outline-offset: 2px; border-radius: 4px; }
.label { font: 600 11px/1 var(--mono); letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }
.num { font-family: var(--mono); font-variant-numeric: tabular-nums; }
.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; }

header { display: flex; flex-wrap: wrap; align-items: end; justify-content: space-between; gap: 12px; }
h1 { font: 800 clamp(28px, 5vw, 44px)/1 var(--display); font-stretch: 112%; letter-spacing: -.01em; margin: 6px 0 0; }
h2 { font: 800 20px/1.1 var(--display); font-stretch: 112%; margin: 0; }
.head-right { display: grid; gap: 10px; justify-items: end; }
.snap { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; color: var(--muted); font-size: 13px; justify-content: flex-end; }
.actions { display: flex; gap: 8px; }
.btn { font: 600 13px var(--body); padding: 8px 14px; border-radius: 8px; border: 1px solid var(--ink); background: var(--ink); color: var(--panel); cursor: pointer; }
.btn.ghost { background: var(--panel); color: var(--ink); border-color: var(--line); }
.btn:disabled { opacity: .55; cursor: progress; }
.pill { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px; font: 600 12px/1.4 var(--mono); border: 1px solid var(--line); }
.pill::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: currentColor; animation: pulse 2.4s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: .35; transform: scale(.75); } }
.s-ok { color: var(--ok); } .s-warn { color: var(--warn); } .s-bad { color: var(--bad); } .s-off { color: var(--off); }
.banner { border-radius: 8px; padding: 12px 16px; font-size: 14px; border: 1px solid currentColor; background: var(--panel); }

.ticker { display: flex; align-items: center; gap: 12px; padding: 8px 0 8px 14px; overflow: hidden; }
.ticker-label { flex: none; }
.ticker-viewport { flex: 1; min-width: 0; overflow: hidden; mask-image: linear-gradient(90deg, transparent, #000 4%, #000 92%, transparent); }
.ticker-track { display: flex; gap: 28px; width: max-content; }
.ticker-item { display: inline-flex; gap: 8px; align-items: baseline; white-space: nowrap; font-size: 13px; text-decoration: none; }
.ticker-item:hover span:last-child { text-decoration: underline; }

.top { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr); gap: 20px; }
.scope { padding: 18px; display: grid; gap: 10px; }
.scope svg { width: 100%; max-width: 520px; height: auto; justify-self: center; overflow: visible; }
.ring { fill: none; stroke: var(--line); } .spoke { stroke: var(--line); }
.sector-label { font: 600 10px var(--mono); letter-spacing: .08em; fill: var(--muted); text-transform: uppercase; }
.ring-label { font: 10px var(--mono); fill: var(--muted); }
.blip { cursor: pointer; outline: none; }
.blip circle.dot { fill: var(--signal); } .blip .halo { fill: var(--signal-soft); }
.blip.dim { opacity: .2; }
.scope-note { color: var(--muted); font-size: 12.5px; text-align: center; }
.readouts { display: grid; gap: 20px; align-content: start; }
.kpis { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; background: var(--line); border-radius: 10px; overflow: hidden; border: 1px solid var(--line); }
.kpi { background: var(--panel); padding: 16px; display: grid; gap: 6px; min-width: 0; }
.kpi b { font: 800 34px/1 var(--display); font-stretch: 112%; font-variant-numeric: tabular-nums; }
.kpi small { color: var(--muted); font-size: 12.5px; overflow-wrap: anywhere; }
.bars-panel { padding: 16px; display: grid; gap: 10px; }
.bar-row { display: grid; grid-template-columns: 112px minmax(0, 1fr) 36px; gap: 10px; align-items: center; font-size: 13px; }
.track { height: 8px; border-radius: 4px; background: var(--signal-soft); overflow: hidden; }
.fill { height: 100%; width: 100%; background: var(--signal); transform-origin: left; border-radius: 4px; }

.tabs { display: flex; flex-wrap: wrap; gap: 4px; border-bottom: 1px solid var(--line); }
.tab { font: 600 14px var(--body); background: none; border: none; color: var(--muted); padding: 10px 14px; cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -1px; }
.tab[aria-selected="true"] { color: var(--ink); border-bottom-color: var(--signal); }
.tabpanel { display: grid; gap: 14px; }
.filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.filters input, .filters select { font: 14px var(--body); color: var(--ink); background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; min-width: 0; }
.filters input { flex: 1 1 220px; }
.count-note { color: var(--muted); font-size: 13px; }

.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 340px), 1fr)); gap: 14px; }
.card { padding: 16px; display: grid; grid-template-columns: 58px minmax(0, 1fr); gap: 14px; align-content: start; cursor: pointer; transition: border-color .2s; }
.card.hot { border-color: var(--signal); }
.dial { position: relative; width: 58px; height: 58px; }
.dial svg { width: 58px; height: 58px; transform: rotate(-90deg); }
.dial .bg { fill: none; stroke: var(--signal-soft); stroke-width: 5; }
.dial .fg { fill: none; stroke: var(--signal); stroke-width: 5; stroke-linecap: round; transition: stroke-dashoffset .9s cubic-bezier(.22, 1, .36, 1); }
.dial span { position: absolute; inset: 0; display: grid; place-items: center; font: 600 15px var(--mono); }
.card h3 { margin: 0 0 4px; font: 600 15.5px/1.3 var(--body); overflow-wrap: anywhere; }
.card h3 a { text-decoration: none; } .card h3 a:hover { text-decoration: underline; }
.meta { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.tag { font: 500 11.5px var(--mono); color: var(--muted); border: 1px solid var(--line); border-radius: 4px; padding: 1px 6px; }
.tag.upd { color: var(--warn); border-color: currentColor; }
.card p { margin: 0; color: var(--muted); font-size: 13.5px; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.mini { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-top: 10px; }
.mini div { display: grid; gap: 3px; } .mini i { display: block; height: 4px; background: var(--signal-soft); border-radius: 2px; overflow: hidden; }
.mini i b { display: block; height: 100%; background: var(--signal); transform-origin: left; }
.mini em { font: 10px var(--mono); color: var(--muted); font-style: normal; }
.details-btn { margin-top: 10px; font: 600 12px var(--mono); color: var(--signal); background: none; border: 1px solid var(--line); border-radius: 6px; padding: 5px 10px; cursor: pointer; }
.details-btn:hover { border-color: var(--signal); }
.empty { padding: 36px 20px; text-align: center; color: var(--muted); }
.empty b { display: block; color: var(--ink); font-size: 16px; margin-bottom: 6px; }

.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
th { text-align: left; padding: 10px 14px; white-space: nowrap; }
td { padding: 10px 14px; border-top: 1px solid var(--line); vertical-align: top; }
td.num, th.num { text-align: right; }
.why { color: var(--muted); font-size: 12.5px; }
.err { color: var(--bad); font-size: 12.5px; overflow-wrap: anywhere; }
.spark rect { fill: var(--signal); }
.runchart { width: 100%; height: auto; display: block; }
.runchart text { font: 10px var(--mono); fill: var(--muted); }
.runchart .grid { stroke: var(--line); }
.item-title { color: var(--signal); text-decoration: none; overflow-wrap: anywhere; } .item-title:hover { text-decoration: underline; }

.backdrop { position: fixed; inset: 0; background: rgba(5, 10, 15, .55); z-index: 40; }
.drawer { position: fixed; top: 0; right: 0; bottom: 0; width: min(560px, 100%); z-index: 41; background: var(--panel); border-left: 1px solid var(--line);
  overflow-y: auto; overscroll-behavior: contain; display: grid; align-content: start; gap: 18px;
  padding: calc(18px + env(safe-area-inset-top, 0px)) max(20px, env(safe-area-inset-right, 0px)) calc(28px + env(safe-area-inset-bottom, 0px)) 22px; }
.d-head { display: grid; grid-template-columns: 64px minmax(0, 1fr) auto; gap: 14px; align-items: start; }
.d-head h2 { font-size: 22px; overflow-wrap: anywhere; }
.d-close { font: 600 18px/1 var(--mono); width: 36px; height: 36px; border-radius: 8px; border: 1px solid var(--line); background: var(--bg); color: var(--ink); cursor: pointer; }
.d-score { width: 64px; height: 64px; border-radius: 50%; display: grid; place-items: center; font: 800 20px var(--display); font-stretch: 112%; border: 3px solid var(--signal); color: var(--signal); }
.d-links { display: flex; flex-wrap: wrap; gap: 8px; }
.d-link { font: 500 13px var(--body); text-decoration: none; padding: 6px 11px; border-radius: 6px; border: 1px solid var(--line); }
.d-link.primary { background: var(--ink); color: var(--panel); border-color: var(--ink); }
.d-sec { display: grid; gap: 6px; }
.d-sec p { margin: 0; line-height: 1.6; }
.d-next { background: var(--signal-soft); border-radius: 8px; padding: 12px 14px; }
.d-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.d-facts { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 6px 14px; font-size: 13px; margin: 0; }
.d-facts dt { color: var(--muted); } .d-facts dd { margin: 0; overflow-wrap: anywhere; }
.d-evidence { margin: 0; padding-left: 18px; display: grid; gap: 4px; font-size: 13.5px; }

.toast { position: fixed; right: max(16px, env(safe-area-inset-right, 0px)); bottom: calc(16px + env(safe-area-inset-bottom, 0px)); z-index: 50; max-width: min(420px, calc(100% - 32px)); }
.foot { color: var(--muted); font-size: 12.5px; }

/* SVG motion runs in CSS: sweep, pings, blip pop/flash/hover, run bars. */
.sweep { transform-origin: 0 0; animation: spin 6s linear infinite; }
.scanning .sweep { animation-duration: 1.5s; }
@keyframes spin { to { transform: rotate(360deg); } }
.ping, .pop, .hov, .flash { transform-box: fill-box; transform-origin: center; }
.ping { opacity: 0; animation: ping 6s ease-out infinite; }
@keyframes ping { 0% { transform: scale(1); opacity: .9; } 23% { transform: scale(3.2); opacity: 0; } 100% { opacity: 0; } }
.flash { animation: flash 6s ease-out infinite; }
@keyframes flash { 0%, 9%, 100% { transform: scale(1); } 3% { transform: scale(1.5); } }
.pop { animation: pop .55s cubic-bezier(.34, 1.56, .64, 1) both; }
@keyframes pop { from { transform: scale(0); opacity: 0; } }
.hov { transition: transform .25s cubic-bezier(.34, 1.56, .64, 1); }
.blip:hover .hov, .blip:focus .hov, .blip.hot .hov { transform: scale(1.6); }
.runchart rect { transform-box: fill-box; transform-origin: bottom; animation: grow .5s ease-out both; }
@keyframes grow { from { transform: scaleY(0); } }

@media (max-width: 820px) { .top { grid-template-columns: minmax(0, 1fr); } .head-right { justify-items: start; } .snap { justify-content: flex-start; } }
@media (max-width: 520px) { .d-grid { grid-template-columns: minmax(0, 1fr); } .bar-row { grid-template-columns: 92px minmax(0, 1fr) 36px; } }
@media (prefers-reduced-motion: reduce) {
  .sweep, .ping, .flash, .pop, .runchart rect, .pill::before { animation: none; }
  .hov, .dial .fg, .card { transition: none; }
  .ticker-viewport { overflow-x: auto; }
}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <div class="label">AI Tech</div>
      <h1>Opportunity Radar</h1>
    </div>
    <div class="head-right">
      <div class="snap"><span id="lastRunPill"></span><span id="lastRunTime">Loading…</span></div>
      <div class="actions">
        <button class="btn ghost" id="refreshBtn" type="button">Refresh</button>
        <button class="btn" id="runBtn" type="button">Run discovery now</button>
      </div>
    </div>
  </header>

  <div id="banner" class="banner" role="status" hidden></div>

  <div class="ticker panel" aria-label="Recently indexed items">
    <span class="label ticker-label">Just indexed</span>
    <div class="ticker-viewport"><div class="ticker-track" id="ticker"><span class="why">Loading…</span></div></div>
  </div>

  <section class="top">
    <div class="panel scope" id="scopePanel" aria-label="Radar scope of the top opportunities">
      <div class="label">Scope · top contacts by source</div>
      <svg id="scope" viewBox="-300 -250 600 500" role="img" aria-label="Top opportunities by source sector; closer to the centre means a higher Radar score"></svg>
      <div class="scope-note" id="scopeNote">Closer to centre = higher Radar score (rings at 88 / 75 / 63 / 50). Click a blip for its full analysis.</div>
    </div>
    <div class="readouts">
      <div class="kpis">
        <div class="kpi"><span class="label">Active opportunities</span><b class="num" id="kOpps">–</b><small>AI-analyzed, deduplicated</small></div>
        <div class="kpi"><span class="label">Highest score</span><b class="num" id="kTop">–</b><small id="kTopName"></small></div>
        <div class="kpi"><span class="label">Indexed records</span><b class="num" id="kIndexed">–</b><small>all sources, incl. jobs</small></div>
        <div class="kpi"><span class="label">Last run collected</span><b class="num" id="kCollected">–</b><small id="kRunNote"></small></div>
      </div>
      <div class="panel bars-panel" aria-label="Source status">
        <div class="label">Sources</div>
        <div id="funnel"></div>
      </div>
      <div class="panel bars-panel" aria-label="Indexed records by type">
        <div class="label">Index by type</div>
        <div id="types"></div>
      </div>
    </div>
  </section>

  <div class="tabs" role="tablist">
    <button class="tab" role="tab" aria-selected="true" data-tab="feed" type="button">Opportunities</button>
    <button class="tab" role="tab" aria-selected="false" data-tab="items" type="button">Discovered items</button>
    <button class="tab" role="tab" aria-selected="false" data-tab="runs" type="button">Run history</button>
    <button class="tab" role="tab" aria-selected="false" data-tab="sources" type="button">Source health</button>
  </div>

  <section class="tabpanel" id="tab-feed" role="tabpanel">
    <div class="filters">
      <input type="search" id="searchInput" placeholder="Search titles, summaries, analysis…" aria-label="Search opportunities">
      <select id="categoryFilter" aria-label="Category">
        <option value="">All categories</option>
        <option value="potential business opportunity">Potential business opportunity</option>
        <option value="potential product idea">Potential product idea</option>
        <option value="technology worth testing">Technology worth testing</option>
        <option value="useful technology">Useful technology</option>
        <option value="interesting technology">Interesting technology</option>
      </select>
      <select id="sourceFilter" aria-label="Source"><option value="">All sources</option></select>
      <select id="typeFilter" aria-label="Type"><option value="">All types</option></select>
      <select id="scoreFilter" aria-label="Minimum score">
        <option value="0">All scores</option><option value="70">Score ≥ 70</option><option value="50">Score ≥ 50</option><option value="30">Score ≥ 30</option>
      </select>
      <select id="sortFilter" aria-label="Sort">
        <option value="score">Highest score</option><option value="newest">Newest discovered</option><option value="verified">Recently verified</option>
      </select>
    </div>
    <div class="count-note" id="feedCount"></div>
    <div class="cards" id="cards"><div class="panel empty"><b>Loading opportunities…</b></div></div>
  </section>

  <section class="tabpanel" id="tab-items" role="tabpanel" hidden>
    <div class="filters">
      <input type="search" id="itemSearch" placeholder="Search indexed items…" aria-label="Search indexed items">
      <select id="itemSourceFilter" aria-label="Source"><option value="">All sources</option></select>
      <select id="itemTypeFilter" aria-label="Type"><option value="">All types</option></select>
    </div>
    <div class="count-note" id="itemCounts"></div>
    <div class="panel table-wrap">
      <table>
        <thead><tr><th class="label">Item</th><th class="label">Type</th><th class="label">Source</th><th class="label">Details</th><th class="label">Published</th><th class="label">First / last seen</th></tr></thead>
        <tbody id="itemsBody"><tr><td colspan="6" class="why">Loading…</td></tr></tbody>
      </table>
    </div>
  </section>

  <section class="tabpanel" id="tab-runs" role="tabpanel" hidden>
    <div class="panel bars-panel">
      <div class="label">Records collected per run</div>
      <svg class="runchart" id="runchart" viewBox="0 0 720 200" role="img" aria-label="Collected records per run, coloured by run status"></svg>
    </div>
    <div class="panel table-wrap">
      <table>
        <thead><tr><th class="label">Run</th><th class="label">Status</th><th class="label">Started</th><th class="label num">Duration</th><th class="label num">Collected</th><th class="label num">New</th><th class="label num">Updated</th><th class="label num">Failed</th><th class="label">Sources</th></tr></thead>
        <tbody id="runsBody"><tr><td colspan="9" class="why">Loading…</td></tr></tbody>
      </table>
    </div>
  </section>

  <section class="tabpanel" id="tab-sources" role="tabpanel" hidden>
    <div class="panel table-wrap">
      <table>
        <thead><tr><th class="label">Source</th><th class="label">Status</th><th class="label num">Last run</th><th class="label num">Indexed</th><th class="label num">Analyzed</th><th class="label">Recent runs</th><th class="label">Last success</th></tr></thead>
        <tbody id="sourcesBody"><tr><td colspan="7" class="why">Loading…</td></tr></tbody>
      </table>
    </div>
  </section>

  <p class="foot">Live data from the local Radar service. Animation by Motion.</p>
</div>

<div class="backdrop" id="backdrop" hidden></div>
<aside class="drawer" id="drawer" role="dialog" aria-modal="true" aria-labelledby="dTitle" hidden></aside>
<div class="toast banner" id="toast" role="status" hidden></div>

<script src="https://cdn.jsdelivr.net/npm/motion@11.11.13/dist/motion.js"></script>
<script>
const M = window.Motion || null;
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches || !M;
const animate = (...a) => (M ? M.animate(...a) : { then: f => f(), stop() {}, pause() {}, play() {} });
const stagger = (...a) => (M ? M.stagger(...a) : 0);
// The page renders finished first; motion starts once it is on screen.
const queued = [];
const later = fn => { if (reduce) return; if (document.visibilityState === "visible") fn(); else queued.push(fn); };
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") queued.splice(0).forEach(fn => fn()); });
const go = (el, kf, opts) => (reduce ? null : later(() => animate(el, kf, opts)));

const NS = "http://www.w3.org/2000/svg";
const svgEl = (tag, attrs, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
const el = (tag, cls, text, parent) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; if (parent) parent.appendChild(e); return e; };
const $ = id => document.getElementById(id);
const safeHref = u => (/^https?:\/\//i.test(String(u || "")) ? String(u) : "#");
const link = (cls, text, href, parent) => { const a = el("a", cls, text, parent); a.href = safeHref(href); a.target = "_blank"; a.rel = "noopener"; return a; };
const TYPES = { open_source: "Open source", product_tool: "Product / tool", model_dataset: "Model / dataset", research_release: "Research", business: "Business / discussion", job: "Jobs" };
const typeLabel = t => TYPES[t] || t || "Unclassified";
const fmtTime = iso => (iso ? new Date(iso).toLocaleString("en-US", { timeZone: "Asia/Manila", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) + " Manila" : "never");
const fmtDate = iso => (iso ? new Date(iso).toLocaleDateString("en-US", { timeZone: "Asia/Manila", month: "short", day: "numeric" }) : "–");
const statusCls = s => ({ ok: "s-ok", success: "s-ok", degraded: "s-warn", partial_failure: "s-warn", failed: "s-bad" })[s] || "s-off";
const pill = (status, text) => el("span", "pill " + statusCls(status), (text || status || "unknown").replace(/_/g, " "));
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name);

const state = { opps: [], runs: [], sources: [], summary: null, items: [], itemCounts: {}, loaded: false };

function toast(msg) {
  const t = $("toast"); t.textContent = msg; t.hidden = false;
  go(t, { opacity: [0, 1], y: [10, 0] }, { duration: .25 });
  clearTimeout(toast._t); toast._t = setTimeout(() => { t.hidden = true; }, 4500);
}
function banner(kind, text) {
  const b = $("banner");
  if (!kind) { b.hidden = true; return; }
  b.className = "banner " + (kind === "error" ? "s-bad" : "s-warn"); b.textContent = text; b.hidden = false;
}

async function getJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} returned HTTP ${res.status}`);
  return res.json();
}

async function loadAllData() {
  try {
    const [opps, runs, src, items] = await Promise.all([
      getJson("/api/opportunities?limit=500"), getJson("/api/runs"), getJson("/api/sources"), getJson("/api/items?limit=500"),
    ]);
    Object.assign(state, {
      opps: opps.opportunities || [], runs: runs.runs || [], sources: src.sources || [], summary: src.summary || null,
      items: items.items || [], itemCounts: items.items_by_type || {}, loaded: true,
    });
    banner(null);
  } catch (err) {
    banner("error", `Disconnected: the local Radar service did not respond (${err.message}). ${state.loaded ? "Showing the last data that loaded." : "No data has loaded yet."}`);
    return;
  }
  renderAll();
}

function renderAll() {
  renderHeader(); renderKpis(); renderBars(); renderScope(); renderTicker();
  fillFilters(); renderFeed(true); renderItems(); renderRuns(); renderSources();
}

// ---- Header, KPIs, bars ------------------------------------------------------------------------
function renderHeader() {
  const last = state.runs[0];
  $("lastRunPill").replaceChildren(last ? pill(last.status) : el("span", "pill s-off", "no runs yet"));
  $("lastRunTime").textContent = last ? "Last run " + fmtTime(last.started_at) : "Pending first run";
  if (last && last.status !== "success") {
    const failing = Object.entries(last.sources || {}).filter(([, s]) => s.status === "failed" || s.status === "degraded").map(([n, s]) => `${n} (${s.status})`);
    banner("warn", `Last run: ${last.status.replace(/_/g, " ")}. ` + (failing.length ? `Sources with errors: ${failing.join(", ")}. ` : "") + `${last.analysis_failed || 0} analysis failure(s). See Run history and Source health.`);
  }
}
function countUp(node, to, dec) {
  const from = parseFloat(node.textContent) || 0;
  node.textContent = to.toFixed(dec);
  later(() => animate(from, to, { duration: 1, ease: "easeOut", onUpdate: v => { node.textContent = v.toFixed(dec); } }));
}
function renderKpis() {
  const top = state.opps.reduce((m, o) => ((o.score || 0) > (m ? m.score || 0 : -1) ? o : m), null);
  const last = state.runs[0];
  countUp($("kOpps"), state.opps.length, 0);
  countUp($("kTop"), top ? top.score || 0 : 0, 1);
  $("kTopName").textContent = top ? top.title : "";
  countUp($("kIndexed"), Object.values(state.itemCounts).reduce((a, b) => a + b, 0), 0);
  countUp($("kCollected"), last ? last.collected || 0 : 0, 0);
  $("kRunNote").textContent = last ? `${last.stored || 0} new · ${last.updated || 0} updated · ${last.failed || 0} failed` : "no runs yet";
}
function barRows(container, rows, max) {
  container.replaceChildren();
  rows.forEach(([name, n], i) => {
    const row = el("div", "bar-row", null, container);
    el("span", null, name, row);
    const f = el("div", "fill", null, el("div", "track", null, row));
    f.style.transform = `scaleX(${max ? n / max : 0})`;
    el("span", "num", String(n), row);
    go(f, { scaleX: [0, max ? n / max : 0] }, { duration: .7, delay: .15 + i * .06, ease: "easeOut" });
  });
}
function renderBars() {
  const s = state.summary || { configured: 0, enabled: 0, healthy: 0, collecting: 0 };
  barRows($("funnel"), [["Configured", s.configured], ["Enabled", s.enabled], ["Healthy", s.healthy], ["Collecting", s.collecting]], s.configured);
  const types = Object.entries(state.itemCounts).sort((a, b) => b[1] - a[1]).map(([t, n]) => [typeLabel(t), n]);
  if (!types.length) { $("types").replaceChildren(el("div", "why", "Nothing indexed yet.")); return; }
  barRows($("types"), types, Math.max(...types.map(t => t[1])));
}

// ---- Scope -------------------------------------------------------------------------------------
const R = 200, SWEEP = 0.6, PERIOD = 6;
let blipLayer = null;
function renderScope() {
  const scope = $("scope"); scope.replaceChildren();
  const sectors = state.sources.filter(s => s.enabled).map(s => s.source_name);
  if (!sectors.length) sectors.push("GitHub");
  [0.25, 0.5, 0.75, 1].forEach(f => {
    svgEl("circle", { class: "ring", r: R * f }, scope);
    svgEl("text", { class: "ring-label", x: 4, y: -R * f + 12 }, scope).textContent = String(Math.round(100 - 50 * f));
  });
  sectors.forEach((name, i) => {
    const a = (i / sectors.length) * Math.PI * 2 - Math.PI / 2, mid = a + Math.PI / sectors.length;
    svgEl("line", { class: "spoke", x1: 0, y1: 0, x2: Math.cos(a) * R, y2: Math.sin(a) * R }, scope);
    svgEl("text", { class: "sector-label", x: Math.cos(mid) * (R + 26), y: Math.sin(mid) * (R + 22), "text-anchor": Math.abs(Math.cos(mid)) < .2 ? "middle" : (Math.cos(mid) > 0 ? "start" : "end"), "dominant-baseline": "middle" }, scope)
      .textContent = name.replace("RSS/Atom Feeds", "RSS / Atom");
  });
  const defs = svgEl("defs", {}, scope);
  const grad = svgEl("linearGradient", { id: "sweepGrad", x1: R * 0.2, y1: 0, x2: 0, y2: R * Math.sin(SWEEP), gradientUnits: "userSpaceOnUse" }, defs);
  svgEl("stop", { offset: "0", "stop-color": css("--signal").trim(), "stop-opacity": ".02" }, grad);
  svgEl("stop", { offset: "1", "stop-color": css("--signal").trim(), "stop-opacity": ".35" }, grad);
  const sweep = svgEl("g", { class: "sweep" }, scope);
  svgEl("path", { d: `M0 0 L${R} 0 A${R} ${R} 0 0 1 ${R * Math.cos(SWEEP)} ${R * Math.sin(SWEEP)} Z`, fill: "url(#sweepGrad)" }, sweep);
  svgEl("line", { x1: 0, y1: 0, x2: R * Math.cos(SWEEP), y2: R * Math.sin(SWEEP), stroke: "var(--signal)", "stroke-width": 1.5, "stroke-linecap": "round" }, sweep);

  blipLayer = svgEl("g", {}, scope);
  const top = [...state.opps].sort((a, b) => (b.score || 0) - (a.score || 0)).slice(0, 12);
  const perSector = {};
  top.forEach((o, idx) => {
    const si = Math.max(0, sectors.indexOf(o.source));
    const k = (perSector[si] = (perSector[si] || 0) + 1);
    const a = (si / sectors.length) * Math.PI * 2 - Math.PI / 2 + (Math.PI * 2 / sectors.length) * (0.2 + ((k * 0.37) % 0.6));
    const rr = Math.min(R - 8, Math.max(16, (100 - (o.score || 0)) / 50 * R));
    const g = svgEl("g", { class: "blip", tabindex: 0, role: "button", "aria-label": `${o.title}, score ${o.score}`, transform: `translate(${Math.cos(a) * rr} ${Math.sin(a) * rr})` }, blipLayer);
    g._opp = o;
    const tau = Math.PI * 2, delay = `${(((a - SWEEP) % tau + tau) % tau) / tau * PERIOD}s`;
    svgEl("circle", { class: "ping", r: 6, fill: "none", stroke: "var(--signal)", "stroke-width": 1.5, style: `animation-delay: ${delay}` }, g);
    const pop = svgEl("g", { class: "pop", style: `animation-delay: ${0.2 + idx * 0.06}s` }, g);
    const inner = svgEl("g", { class: "flash", style: `animation-delay: ${delay}` }, svgEl("g", { class: "hov" }, pop));
    svgEl("circle", { class: "halo", r: 11 }, inner);
    svgEl("circle", { class: "dot", r: 4.5 }, inner);
    svgEl("title", {}, g).textContent = `${o.title} · ${o.score}`;
    const hot = on => { g.classList.toggle("hot", on); document.querySelectorAll(".card").forEach(c => c._opp === o && c.classList.toggle("hot", on)); };
    g.addEventListener("mouseenter", () => hot(true)); g.addEventListener("mouseleave", () => hot(false));
    g.addEventListener("focus", () => hot(true)); g.addEventListener("blur", () => hot(false));
    g.addEventListener("click", () => openDetail(o, g));
    g.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openDetail(o, g); } });
  });
  $("scopeNote").textContent = top.length
    ? "Closer to centre = higher Radar score (rings at 88 / 75 / 63 / 50). Click a blip for its full analysis."
    : "No analyzed opportunities yet. Run discovery to populate the scope.";
}

// ---- Ticker ------------------------------------------------------------------------------------
let tickerAnim = null;
function renderTicker() {
  const ticker = $("ticker"); if (tickerAnim) tickerAnim.stop(); ticker.style.transform = "";
  ticker.replaceChildren();
  const recent = state.items.slice(0, 16);
  if (!recent.length) { el("span", "why", "Nothing indexed yet.", ticker); return; }
  for (let copy = 0; copy < 2; copy++) recent.forEach(i => {
    const a = link("ticker-item", null, i.url, ticker);
    if (copy) { a.setAttribute("aria-hidden", "true"); a.tabIndex = -1; }
    el("span", "tag", i.source.replace("RSS/Atom Feeds", "RSS"), a); el("span", null, i.title, a);
  });
  later(() => {
    const half = ticker.scrollWidth / 2;
    tickerAnim = animate(ticker, { x: [0, -half] }, { duration: half / 40, ease: "linear", repeat: Infinity });
  });
}
$("ticker").addEventListener("pointerenter", () => tickerAnim && tickerAnim.pause());
$("ticker").addEventListener("pointerleave", () => tickerAnim && tickerAnim.play());

// ---- Filters -----------------------------------------------------------------------------------
function fillSelect(id, values, label) {
  const s = $(id), current = s.value;
  s.replaceChildren(new Option(label, ""));
  values.forEach(([v, t]) => s.add(new Option(t, v)));
  s.value = values.some(([v]) => v === current) ? current : "";
}
function fillFilters() {
  const sources = [...new Set([...state.opps.map(o => o.source || "GitHub"), ...state.sources.filter(s => s.enabled).map(s => s.source_name)])].sort();
  fillSelect("sourceFilter", sources.map(s => [s, s]), "All sources");
  fillSelect("typeFilter", [...new Set(state.opps.map(o => o.item_type || ""))].sort().map(t => [t, typeLabel(t)]), "All types");
  fillSelect("itemSourceFilter", [...new Set(state.items.map(i => i.source))].sort().map(s => [s, s]), "All sources");
  fillSelect("itemTypeFilter", Object.keys(state.itemCounts).sort().map(t => [t, `${typeLabel(t)} (${state.itemCounts[t]})`]), "All types");
}
["searchInput", "categoryFilter", "sourceFilter", "typeFilter", "scoreFilter", "sortFilter"].forEach(id => $(id).addEventListener(id === "searchInput" ? "input" : "change", () => renderFeed(false)));
["itemSearch", "itemSourceFilter", "itemTypeFilter"].forEach(id => $(id).addEventListener(id === "itemSearch" ? "input" : "change", renderItems));

// ---- Opportunity cards -------------------------------------------------------------------------
const C = 2 * Math.PI * 24;
function drawDial(fg, score) {
  fg.style.strokeDashoffset = C * (1 - score / 100);
  if (reduce) return;
  later(() => { fg.style.transition = "none"; fg.style.strokeDashoffset = C; fg.getBoundingClientRect(); fg.style.transition = ""; fg.style.strokeDashoffset = C * (1 - score / 100); });
}
function renderFeed(fromLoad) {
  const search = $("searchInput").value.toLowerCase(), cat = $("categoryFilter").value, src = $("sourceFilter").value;
  const type = $("typeFilter").value, minScore = parseFloat($("scoreFilter").value) || 0, sort = $("sortFilter").value;
  const list = state.opps.filter(o => {
    if (cat && o.category !== cat) return false;
    if (src && (o.source || "GitHub") !== src && !(o.supporting_sources || []).some(s => s.source === src)) return false;
    if (type && (o.item_type || "") !== type) return false;
    if ((o.score || 0) < minScore) return false;
    if (search && !`${o.title} ${o.summary || ""} ${o.what_it_does || ""} ${o.why_it_matters || ""}`.toLowerCase().includes(search)) return false;
    return true;
  });
  const by = { score: (a, b) => (b.score || 0) - (a.score || 0), newest: (a, b) => new Date(b.date_discovered || 0) - new Date(a.date_discovered || 0), verified: (a, b) => new Date(b.last_verified || 0) - new Date(a.last_verified || 0) };
  list.sort(by[sort] || by.score);
  if (blipLayer) blipLayer.querySelectorAll(".blip").forEach(g => g.classList.toggle("dim", !list.includes(g._opp)));
  $("feedCount").textContent = state.opps.length ? `Showing ${list.length} of ${state.opps.length} opportunities` : "";

  const cards = $("cards"); cards.replaceChildren();
  if (!list.length) {
    const e = el("div", "panel empty", null, cards);
    el("b", null, state.opps.length ? "No opportunities match these filters" : "No analyzed opportunities yet", e);
    el("span", null, state.opps.length ? "Try relaxing the filters." : "Run discovery to collect and analyze items from the enabled sources.", e);
    return;
  }
  list.forEach(o => {
    const card = el("article", "panel card", null, cards); card._opp = o;
    const dial = el("div", "dial", null, card);
    const sv = svgEl("svg", { viewBox: "0 0 58 58", "aria-hidden": "true" }, dial);
    svgEl("circle", { class: "bg", cx: 29, cy: 29, r: 24 }, sv);
    const fg = svgEl("circle", { class: "fg", cx: 29, cy: 29, r: 24, "stroke-dasharray": C }, sv);
    el("span", null, Math.round(o.score || 0), dial);
    const body = el("div", null, null, card);
    link(null, o.title, o.url, el("h3", null, null, body));
    const meta = el("div", "meta", null, body);
    el("span", "tag", o.source || "GitHub", meta);
    if (o.item_type) el("span", "tag", typeLabel(o.item_type), meta);
    if (o.category) el("span", "tag", o.category, meta);
    if ((o.source || "GitHub") === "GitHub" && o.github_stars != null) el("span", "tag", `★ ${Number(o.github_stars).toLocaleString("en-US")}`, meta);
    if (o.update_reason) { const u = el("span", "tag upd", "updated", meta); u.title = o.update_reason; }
    (o.supporting_sources || []).slice(0, 2).forEach(s => el("span", "tag", "also " + s.source, meta));
    el("p", null, o.summary || "", body);
    const mini = el("div", "mini", null, body);
    [["relevance", "rel"], ["demand", "dem"], ["recency", "rec"], ["actionability", "act"], ["evidence_quality", "evd"]].forEach(([k, lab]) => {
      const v = (o.score_breakdown || {})[k] || 0, b = el("div", null, null, mini); b.title = `${k.replace("_", " ")}: ${v}`;
      el("b", null, null, el("i", null, null, b)).style.transform = `scaleX(${v / 100})`;
      el("em", null, lab, b);
    });
    const more = el("button", "details-btn", "View full analysis →", body); more.type = "button";
    card.addEventListener("click", e => { if (!e.target.closest("a")) openDetail(o, more); });
    if (!reduce) {
      card.addEventListener("pointerenter", () => { animate(card, { y: -4 }, { type: "spring", bounce: 0.25, visualDuration: 0.3 }); drawDial(fg, o.score || 0); });
      card.addEventListener("pointerleave", () => animate(card, { y: 0 }, { type: "spring", bounce: 0, visualDuration: 0.3 }));
    }
    drawDial(fg, o.score || 0);
  });
  go([...cards.children], { opacity: [0, 1], y: [10, 0] }, { duration: .35, ease: "easeOut", delay: stagger(fromLoad ? .04 : .025) });
}

// ---- Discovered items --------------------------------------------------------------------------
function renderItems() {
  const search = $("itemSearch").value.toLowerCase(), src = $("itemSourceFilter").value, type = $("itemTypeFilter").value;
  const rows = state.items.filter(i => (!src || i.source === src) && (!type || i.item_type === type) && (!search || `${i.title} ${i.description || ""}`.toLowerCase().includes(search)));
  const total = Object.values(state.itemCounts).reduce((a, b) => a + b, 0);
  $("itemCounts").textContent = `${total} records indexed across sources (showing ${rows.length} of the ${state.items.length} most recent). AI analysis runs on a small budgeted subset; jobs are indexed without analysis.`;
  const tbody = $("itemsBody"); tbody.replaceChildren();
  if (!rows.length) { const td = el("td", "why", state.items.length ? "No items match these filters." : "Nothing indexed yet. Items appear after the first multi-source discovery run.", el("tr", null, null, tbody)); td.colSpan = 6; return; }
  rows.forEach(i => {
    const tr = el("tr", null, null, tbody), ev = i.evidence || {};
    link("item-title", i.title, i.url, el("td", null, null, tr));
    el("td", null, typeLabel(i.item_type), tr); el("td", null, i.source, tr);
    const d = el("td", "why", null, tr), parts = [];
    if (i.item_type === "job") {
      if (ev.employer) parts.push(`Employer: ${ev.employer}`); if (ev.location) parts.push(`Location: ${ev.location}`);
      if (ev.job_type) parts.push(String(ev.job_type).replace(/_/g, " ")); if (ev.salary) parts.push(`Salary (as listed): ${ev.salary}`);
    } else {
      if (ev.stars != null) parts.push(`★ ${Number(ev.stars).toLocaleString()}`); if (ev.likes != null) parts.push(`♥ ${Number(ev.likes).toLocaleString()} likes`);
      if (ev.downloads != null) parts.push(`${Number(ev.downloads).toLocaleString()} downloads`); if (ev.points != null) parts.push(`${ev.points} points, ${ev.comments || 0} comments`);
      if (ev.publisher) parts.push(ev.publisher); else if (i.author) parts.push(`by ${i.author}`);
      if (i.analyzed) parts.push("analyzed");
    }
    d.textContent = parts.join(" · ");
    if (i.item_type === "job") { d.append(" · "); link(null, "Apply via Remotive ↗", ev.application_url || i.url, d); }
    else if (ev.discussion_url) { d.append(" · "); link(null, "discussion ↗", ev.discussion_url, d); }
    (i.supporting || []).forEach(s => { d.append(" · "); link(null, `also on ${s.source} ↗`, s.url, d); });
    el("td", "why", fmtDate(i.published_at), tr);
    el("td", "why", `${fmtDate(i.first_seen)} / ${fmtDate(i.last_seen)} (${i.seen_count}×)`, tr);
  });
}

// ---- Runs --------------------------------------------------------------------------------------
function renderRuns() {
  const tbody = $("runsBody"); tbody.replaceChildren();
  const rc = $("runchart"); rc.replaceChildren();
  if (!state.runs.length) { const td = el("td", "why", "No pipeline runs recorded yet.", el("tr", null, null, tbody)); td.colSpan = 9; return; }
  state.runs.forEach(r => {
    const tr = el("tr", null, null, tbody);
    el("td", "why", r.run_id, tr); el("td", null, null, tr).appendChild(pill(r.status));
    el("td", "why", fmtTime(r.started_at), tr);
    el("td", "num", r.duration_seconds != null ? `${r.duration_seconds}s` : "–", tr);
    el("td", "num", String(r.collected || 0), tr); el("td", "num", `+${r.stored || 0}`, tr);
    el("td", "num", String(r.updated || 0), tr); el("td", "num" + (r.failed ? " err" : ""), String(r.failed || 0), tr);
    const s = el("td", "why", null, tr);
    Object.entries(r.sources || {}).filter(([, v]) => v.status !== "disabled").forEach(([n, v]) => el("div", null, `${n}: ${v.status}${v.status === "skipped" ? "" : ` (${v.collected || 0})`}`, s));
    (r.errors || []).slice(0, 3).forEach(e => el("div", "err", `${e.query || e.title || ""}: ${e.error || ""}`, s));
  });
  const asc = [...state.runs].reverse(), W = 720, H = 200, pad = { l: 34, r: 8, t: 14, b: 34 };
  const yMax = Math.max(50, Math.ceil(Math.max(...asc.map(r => r.collected || 0)) / 50) * 50), bw = (W - pad.l - pad.r) / asc.length;
  [0, yMax / 2, yMax].forEach(v => {
    const y = pad.t + (H - pad.t - pad.b) * (1 - v / yMax);
    svgEl("line", { class: "grid", x1: pad.l, x2: W - pad.r, y1: y, y2: y }, rc);
    svgEl("text", { x: pad.l - 6, y: y + 3, "text-anchor": "end" }, rc).textContent = v;
  });
  const colour = s => css(s === "success" ? "--ok" : s === "failed" ? "--bad" : "--warn");
  asc.forEach((r, i) => {
    const h = (H - pad.t - pad.b) * (r.collected || 0) / yMax, x = pad.l + i * bw + bw * .2;
    const rect = svgEl("rect", { x, y: H - pad.b - h, width: bw * .6, height: h, rx: 3, fill: colour(r.status), style: `animation-delay: ${0.2 + i * 0.04}s` }, rc);
    svgEl("title", {}, rect).textContent = `${fmtTime(r.started_at)}: ${r.collected} collected, ${r.status.replace(/_/g, " ")}`;
    if (asc.length <= 12 || i % 2 === 0) svgEl("text", { x: x + bw * .3, y: H - pad.b + 14, "text-anchor": "middle" }, rc).textContent = fmtDate(r.started_at);
    svgEl("text", { x: x + bw * .3, y: H - pad.b - h - 4, "text-anchor": "middle" }, rc).textContent = r.collected;
  });
}

// ---- Sources -----------------------------------------------------------------------------------
function renderSources() {
  const tbody = $("sourcesBody"); tbody.replaceChildren();
  if (!state.sources.length) { const td = el("td", "why", "The service returned no configured sources.", el("tr", null, null, tbody)); td.colSpan = 7; return; }
  const asc = [...state.runs].slice(0, 8).reverse();
  state.sources.forEach(s => {
    const tr = el("tr", null, null, tbody), name = el("td", null, null, tr);
    el("div", null, s.source_name, name);
    if (s.access) el("div", "why", s.access, name);
    if (!s.enabled && s.disabled_reason) el("div", "why", "Disabled: " + s.disabled_reason, name);
    if (s.enabled && s.min_interval_minutes) el("div", "why", `Polls at most every ${s.min_interval_minutes} min`, name);
    if (s.last_error) el("div", "err", "Last error: " + s.last_error, name);
    const st = el("td", null, null, tr);
    st.appendChild(s.enabled ? pill(s.last_status) : el("span", "pill s-off", "disabled"));
    if (s.collecting) { st.append(" "); st.appendChild(el("span", "pill s-ok", "collecting")); }
    el("td", "num", s.enabled ? `${s.items_collected || 0}${s.requests_failed ? ` (${s.requests_failed} req. failed)` : ""}` : "–", tr);
    el("td", "num", s.enabled ? String(s.indexed_items || 0) : "–", tr);
    el("td", "num", s.enabled ? String(s.opportunities || 0) : "–", tr);
    const sp = el("td", null, null, tr);
    if (s.enabled && asc.length) {
      const vals = asc.map(r => ((r.sources || {})[s.source_name] || {}).collected || 0), mx = Math.max(1, ...vals);
      const svg = svgEl("svg", { class: "spark", width: 96, height: 22, viewBox: "0 0 96 22", role: "img", "aria-label": `Collected per run: ${vals.join(", ")}` }, sp);
      vals.forEach((v, i) => svgEl("rect", { x: i * 12, y: 22 - Math.max(1.5, v / mx * 22), width: 8, height: Math.max(1.5, v / mx * 22), rx: 1.5, opacity: v ? 1 : .25 }, svg));
    }
    el("td", "why", s.enabled ? fmtTime(s.last_success_at) : "", tr);
  });
}

// ---- Tabs --------------------------------------------------------------------------------------
document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(t => t.setAttribute("aria-selected", String(t === tab)));
  ["feed", "items", "runs", "sources"].forEach(n => { $("tab-" + n).hidden = n !== tab.dataset.tab; });
  go($("tab-" + tab.dataset.tab), { opacity: [0, 1], y: [6, 0] }, { duration: .25 });
}));

// ---- Run discovery -----------------------------------------------------------------------------
$("refreshBtn").addEventListener("click", loadAllData);
$("runBtn").addEventListener("click", async () => {
  const btn = $("runBtn"); btn.disabled = true; btn.textContent = "Scanning…"; $("scopePanel").classList.add("scanning");
  toast("Discovery started: collecting from enabled sources and analyzing a capped number of items.");
  try {
    const res = await fetch("/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    const data = await res.json().catch(() => ({}));
    if (res.status === 409) toast("A Radar run is already in progress.");
    else if (res.ok) { toast(`Run ${String(data.status || "complete").replace(/_/g, " ")}: ${data.stored || 0} new, ${data.updated || 0} updated, ${data.failed || 0} failed.`); await loadAllData(); }
    else toast(`Run error: ${data.error || "HTTP " + res.status}`);
  } catch (err) {
    toast("Could not reach the Radar service to start a run.");
  } finally {
    btn.disabled = false; btn.textContent = "Run discovery now"; $("scopePanel").classList.remove("scanning");
  }
});

// ---- Details drawer ----------------------------------------------------------------------------
const drawer = $("drawer"), backdrop = $("backdrop");
const LABELS = { relevance: "Relevance", demand: "Demand", recency: "Recency", actionability: "Actionability", evidence_quality: "Evidence quality" };
let opener = null;
function section(parent, label, text, cls) {
  if (!text) return;
  const s = el("section", "d-sec" + (cls ? " " + cls : ""), null, parent);
  el("div", "label", label, s); el("p", null, text, s);
}
function openDetail(o, from) {
  opener = from || null;
  drawer.replaceChildren();
  const head = el("div", "d-head", null, drawer);
  el("div", "d-score", Math.round(o.score || 0), head);
  const ht = el("div", null, null, head);
  el("div", "label", `${o.source || "GitHub"} · ${typeLabel(o.item_type)}`, ht);
  el("h2", null, o.title, ht).id = "dTitle";
  const close = el("button", "d-close", "×", head); close.type = "button"; close.setAttribute("aria-label", "Close details");
  close.addEventListener("click", closeDetail);
  const links = el("div", "d-links", null, drawer);
  link("d-link primary", `Open on ${o.source || "GitHub"} ↗`, o.url, links);
  (o.supporting_sources || []).forEach(s => link("d-link", `Also on ${s.source} ↗`, s.url, links));
  section(drawer, "Summary", o.summary);
  section(drawer, "Recommended next action", o.recommended_next_action, "d-next");
  section(drawer, "What it does", o.what_it_does);
  section(drawer, "Why it matters", o.why_it_matters);
  section(drawer, "Potential use for us", o.potential_use_for_us);
  const grid = el("div", "d-grid", null, drawer);
  section(grid, "Business opportunity", o.business_opportunity);
  section(grid, "Technical opportunity", o.technical_opportunity);
  const bd = el("section", "d-sec", null, drawer); el("div", "label", "Score breakdown", bd);
  const rows = el("div", null, null, bd); rows.style.display = "grid"; rows.style.gap = "8px";
  Object.entries(o.score_breakdown || {}).forEach(([k, v], n) => {
    const row = el("div", "bar-row", null, rows);
    el("span", null, LABELS[k] || k, row);
    const f = el("div", "fill", null, el("div", "track", null, row)); f.style.transform = `scaleX(${v / 100})`;
    el("span", "num", String(v), row);
    if (!reduce) animate(f, { scaleX: [0, v / 100] }, { duration: .6, delay: .15 + n * .05, ease: "easeOut" });
  });
  const ev = Array.isArray(o.evidence) ? o.evidence : [];
  if (ev.length) {
    const es = el("section", "d-sec", null, drawer); el("div", "label", "Evidence cited by the analysis", es);
    const ul = el("ul", "d-evidence", null, es); ev.forEach(e => el("li", null, String(e), ul));
  }
  const fs = el("section", "d-sec", null, drawer); el("div", "label", "Record", fs);
  const dl = el("dl", "d-facts", null, fs);
  const fact = (k, v) => { if (v == null || v === "") return; el("dt", null, k, dl); el("dd", null, String(v), dl); };
  fact("Category", o.category); fact("Confidence", o.confidence); fact("Estimated effort", o.estimated_effort);
  if ((o.source || "GitHub") === "GitHub" && o.github_stars != null) fact("GitHub stars", Number(o.github_stars).toLocaleString("en-US"));
  fact("Update", o.update_reason); fact("First discovered", fmtTime(o.date_discovered));
  if (o.last_verified) fact("Last verified", fmtTime(o.last_verified));
  if (o.last_seen) fact("Last seen in a source", fmtTime(o.last_seen));

  backdrop.hidden = false; drawer.hidden = false; drawer.scrollTop = 0; document.body.style.overflow = "hidden";
  if (!reduce) {
    animate(backdrop, { opacity: [0, 1] }, { duration: .2 });
    animate(drawer, { x: ["100%", "0%"] }, { type: "spring", bounce: 0.12, visualDuration: 0.4 });
    animate([...drawer.children].slice(1), { opacity: [0, 1], y: [12, 0] }, { duration: .3, delay: stagger(.04, { startDelay: .12 }) });
  }
  close.focus();
}
function closeDetail() {
  if (drawer.hidden) return;
  const done = () => { if (drawer.hidden) return; drawer.hidden = true; backdrop.hidden = true; document.body.style.overflow = ""; if (opener && opener.isConnected && opener.focus) opener.focus(); };
  if (reduce) return done();
  animate(backdrop, { opacity: 0 }, { duration: .18 });
  animate(drawer, { x: "100%" }, { duration: .22, ease: "easeIn" });
  setTimeout(done, 240); // a timer, not the animation promise: it must close even when frames are throttled
}
backdrop.addEventListener("click", closeDetail);
document.addEventListener("keydown", e => {
  if (drawer.hidden) return;
  if (e.key === "Escape") closeDetail();
  if (e.key === "Tab") { // keep focus inside the open dialog
    const f = [...drawer.querySelectorAll("a, button")], first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
});

loadAllData();
</script>
</body>
</html>
"""
