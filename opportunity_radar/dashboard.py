from __future__ import annotations

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Tech Opportunity Radar</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --card-hover: #24344d;
      --border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --purple: #a855f7;
      --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: var(--font);
      line-height: 1.5;
      padding-bottom: 60px;
    }
    header {
      background: #090e17;
      border-bottom: 1px solid var(--border);
      padding: 18px 32px;
      position: sticky;
      top: 0;
      z-index: 50;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-icon {
      width: 36px;
      height: 36px;
      background: linear-gradient(135deg, #0284c7, #9333ea);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
    }
    .brand-title {
      font-size: 1.25rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }
    .brand-tagline {
      font-size: 0.8rem;
      color: var(--text-muted);
    }
    .header-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .btn {
      background: var(--accent);
      color: #0f172a;
      border: none;
      border-radius: 6px;
      padding: 8px 16px;
      font-weight: 600;
      font-size: 0.875rem;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: background 0.15s ease;
    }
    .btn:hover { background: var(--accent-hover); color: #fff; }
    .btn:disabled { opacity: 0.6; cursor: not-allowed; }
    .btn-secondary {
      background: #334155;
      color: var(--text);
    }
    .btn-secondary:hover { background: #475569; }
    .nav-tabs {
      display: flex;
      gap: 8px;
      margin: 24px 32px 0 32px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 12px;
    }
    .tab-btn {
      background: none;
      border: none;
      color: var(--text-muted);
      padding: 8px 16px;
      border-radius: 6px;
      font-size: 0.95rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .tab-btn.active {
      color: var(--accent);
      background: rgba(56, 189, 248, 0.1);
    }
    .tab-btn:hover:not(.active) { color: var(--text); }
    main {
      padding: 24px 32px;
      max-width: 1400px;
      margin: 0 auto;
    }
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .stat-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
    }
    .stat-label {
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      margin-bottom: 6px;
    }
    .stat-value {
      font-size: 1.75rem;
      font-weight: 700;
    }
    .filters-bar {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 24px;
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
    }
    .search-box {
      flex: 1;
      min-width: 240px;
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px 14px;
      color: var(--text);
      font-size: 0.9rem;
    }
    .search-box:focus { outline: 1px solid var(--accent); }
    .select-box {
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px 14px;
      color: var(--text);
      font-size: 0.9rem;
    }
    .feed-grid {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 20px;
      transition: border-color 0.15s ease, background 0.15s ease;
    }
    .card:hover {
      border-color: #475569;
      background: var(--card-hover);
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 12px;
    }
    .card-title-area {
      flex: 1;
    }
    .card-title {
      font-size: 1.25rem;
      font-weight: 700;
      color: var(--accent);
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    .card-title:hover { text-decoration: underline; }
    .card-meta-row {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-top: 6px;
      flex-wrap: wrap;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      padding: 3px 8px;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: capitalize;
    }
    .badge-business { background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.4); }
    .badge-product { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }
    .badge-testing { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
    .badge-useful { background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4); }
    .badge-interesting { background: rgba(148, 163, 184, 0.2); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.4); }
    .badge-source { background: #334155; color: #f1f5f9; }
    .score-badge {
      font-size: 1.1rem;
      font-weight: 800;
      padding: 6px 14px;
      border-radius: 8px;
      display: flex;
      flex-direction: column;
      align-items: center;
      min-width: 70px;
      text-align: center;
    }
    .score-high { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #059669; }
    .score-med { background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid #0284c7; }
    .score-mod { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #d97706; }
    .score-low { background: rgba(148, 163, 184, 0.2); color: #94a3b8; border: 1px solid #475569; }
    .score-sub { font-size: 0.65rem; font-weight: 400; opacity: 0.8; }
    .summary-text {
      color: #e2e8f0;
      font-size: 0.95rem;
      margin-bottom: 16px;
    }
    .card-grid-details {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }
    .detail-box {
      background: rgba(15, 23, 42, 0.6);
      border: 1px solid rgba(51, 65, 85, 0.5);
      border-radius: 6px;
      padding: 10px 14px;
    }
    .detail-label {
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      margin-bottom: 4px;
    }
    .detail-content {
      font-size: 0.875rem;
      color: #cbd5e1;
    }
    .action-box {
      background: rgba(56, 189, 248, 0.08);
      border-left: 3px solid var(--accent);
      border-radius: 0 6px 6px 0;
      padding: 10px 14px;
      margin-bottom: 16px;
    }
    .action-label {
      font-size: 0.75rem;
      font-weight: 700;
      color: var(--accent);
      text-transform: uppercase;
      margin-bottom: 2px;
    }
    .card-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-top: 1px solid rgba(51, 65, 85, 0.5);
      padding-top: 12px;
      font-size: 0.8rem;
      color: var(--text-muted);
      flex-wrap: wrap;
      gap: 8px;
    }
    .evidence-tags {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .evidence-pill {
      background: #0f172a;
      border: 1px solid var(--border);
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 0.75rem;
    }
    .table-container {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow-x: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 0.875rem;
    }
    th, td {
      padding: 12px 16px;
      border-bottom: 1px solid var(--border);
    }
    th {
      background: #090e17;
      color: var(--text-muted);
      font-weight: 600;
      text-transform: uppercase;
      font-size: 0.75rem;
    }
    tr:last-child td { border-bottom: none; }
    .status-pill {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
    }
    .status-success { background: rgba(16, 185, 129, 0.2); color: #34d399; }
    .status-partial { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
    .status-failure { background: rgba(239, 68, 68, 0.2); color: #f87171; }
    .empty-state {
      text-align: center;
      padding: 48px 20px;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
    }
    .empty-icon { font-size: 40px; margin-bottom: 12px; }
    .empty-title { font-size: 1.15rem; font-weight: 600; margin-bottom: 8px; }
    .empty-desc { color: var(--text-muted); font-size: 0.9rem; max-width: 480px; margin: 0 auto; }
    .banner {
      border-radius: 8px;
      padding: 12px 16px;
      margin-bottom: 24px;
      font-size: 0.9rem;
      border: 1px solid;
    }
    .banner-error { background: rgba(239, 68, 68, 0.12); border-color: #b91c1c; color: #fca5a5; }
    .banner-warn { background: rgba(245, 158, 11, 0.12); border-color: #b45309; color: #fcd34d; }
    .status-muted { background: rgba(148, 163, 184, 0.2); color: #cbd5e1; }
    .notification {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #1e293b;
      border: 1px solid var(--accent);
      border-radius: 8px;
      padding: 14px 20px;
      color: #fff;
      font-size: 0.9rem;
      box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5);
      z-index: 100;
      display: none;
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="brand-icon">📡</div>
      <div>
        <div class="brand-title">AI Tech Opportunity Radar</div>
        <div class="brand-tagline">Continuous AI, Automation, MCP & Tech Opportunity Engine</div>
      </div>
    </div>
    <div class="header-actions">
      <button class="btn btn-secondary" onclick="loadAllData()">↻ Refresh</button>
      <button class="btn" id="runBtn" onclick="triggerDiscoveryRun()">⚡ Run Discovery Now</button>
    </div>
  </header>

  <div class="nav-tabs">
    <button class="tab-btn active" onclick="switchTab('feed')">🎯 Opportunities Feed</button>
    <button class="tab-btn" onclick="switchTab('items')">🗂️ Discovered Items</button>
    <button class="tab-btn" onclick="switchTab('runs')">📊 Run History & Observability</button>
    <button class="tab-btn" onclick="switchTab('sources')">🌐 Source Health</button>
  </div>

  <main>
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Active Opportunities</div>
        <div class="stat-value" id="statTotalOpps">-</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Highest Score</div>
        <div class="stat-value" id="statTopScore" style="color: var(--accent);">-</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Sources: configured / enabled</div>
        <div class="stat-value" id="statSourcesCount">-</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Sources: healthy / collecting</div>
        <div class="stat-value" id="statSourcesHealthy">-</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Last Discovery Run</div>
        <div class="stat-value" id="statLastRun" style="font-size: 1.1rem; padding-top: 6px;">-</div>
        <div id="statLastRunStatus" style="margin-top: 4px;"></div>
      </div>
    </div>
    <div id="statusBanner" class="banner" style="display: none;"></div>

    <!-- TAB 1: OPPORTUNITIES FEED -->
    <div id="tabFeed">
      <div class="filters-bar">
        <input type="text" class="search-box" id="searchInput" placeholder="Search titles, summaries, topics..." oninput="filterFeed()">
        <select class="select-box" id="categoryFilter" onchange="filterFeed()">
          <option value="">All Categories</option>
          <option value="potential business opportunity">Potential Business Opportunity</option>
          <option value="potential product idea">Potential Product Idea</option>
          <option value="technology worth testing">Technology Worth Testing</option>
          <option value="useful technology">Useful Technology</option>
          <option value="interesting technology">Interesting Technology</option>
        </select>
        <select class="select-box" id="sourceFilter" onchange="filterFeed()">
          <option value="">All Sources</option>
        </select>
        <select class="select-box" id="typeFilter" onchange="filterFeed()">
          <option value="">All Types</option>
        </select>
        <select class="select-box" id="scoreFilter" onchange="filterFeed()">
          <option value="0">All Scores</option>
          <option value="70">Score ≥ 70</option>
          <option value="50">Score ≥ 50</option>
          <option value="30">Score ≥ 30</option>
        </select>
        <select class="select-box" id="sortFilter" onchange="filterFeed()">
          <option value="score">Sort: Highest Score</option>
          <option value="newest">Sort: Newest Discovered</option>
          <option value="verified">Sort: Recently Verified</option>
        </select>
      </div>

      <div class="feed-grid" id="opportunitiesContainer">
        <div class="empty-state"><div class="empty-title">Loading opportunities…</div></div>
      </div>
    </div>

    <!-- TAB: DISCOVERED ITEMS (every indexed record, incl. jobs; only a budgeted subset is AI-analyzed) -->
    <div id="tabItems" style="display: none;">
      <div class="filters-bar">
        <input type="text" class="search-box" id="itemSearch" placeholder="Search indexed items..." oninput="renderItems()">
        <select class="select-box" id="itemSourceFilter" onchange="renderItems()"><option value="">All Sources</option></select>
        <select class="select-box" id="itemTypeFilter" onchange="renderItems()"><option value="">All Types</option></select>
      </div>
      <div id="itemCounts" style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 12px;"></div>
      <div class="table-container">
        <table>
          <thead><tr><th>Item</th><th>Type</th><th>Source</th><th>Details</th><th>Published</th><th>First / last seen</th></tr></thead>
          <tbody id="itemsTableBody"><tr><td colspan="6" style="text-align:center; color: var(--text-muted); padding: 24px;">Loading…</td></tr></tbody>
        </table>
      </div>
    </div>

    <!-- TAB 2: RUN HISTORY -->
    <div id="tabRuns" style="display: none;">
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Run ID</th>
              <th>Status</th>
              <th>Started At</th>
              <th>Duration</th>
              <th>Collected</th>
              <th>Stored</th>
              <th>Updated</th>
              <th>Failed</th>
              <th>Sources</th>
            </tr>
          </thead>
          <tbody id="runsTableBody">
            <!-- Injected via JavaScript -->
          </tbody>
        </table>
      </div>
    </div>

    <!-- TAB 3: SOURCE HEALTH -->
    <div id="tabSources" style="display: none;">
      <div class="stats-grid" id="sourcesContainer">
        <!-- Injected via JavaScript -->
      </div>
    </div>
  </main>

  <div class="notification" id="notif"></div>

  <script>
    let allOpportunities = [];
    let allRuns = [];
    let allSources = [];
    let sourceSummary = null;
    let allItems = [];
    let itemCounts = {};
    const TYPE_LABELS = {
      product_tool: 'AI product / tool', open_source: 'Open-source project', model_dataset: 'Model / dataset',
      research_release: 'Research / release', business: 'Business / discussion', job: 'Job / freelance'
    };
    const typeLabel = t => TYPE_LABELS[t] || (t ? t : 'Unclassified');

    function switchTab(tab) {
      document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
      event.target.classList.add('active');
      document.getElementById('tabFeed').style.display = tab === 'feed' ? 'block' : 'none';
      document.getElementById('tabItems').style.display = tab === 'items' ? 'block' : 'none';
      document.getElementById('tabRuns').style.display = tab === 'runs' ? 'block' : 'none';
      document.getElementById('tabSources').style.display = tab === 'sources' ? 'block' : 'none';
    }

    function fillSelect(id, values, label) {
      const el = document.getElementById(id);
      const current = el.value;
      el.innerHTML = `<option value="">${label}</option>` + values.map(v =>
        `<option value="${escapeHtml(v.value)}">${escapeHtml(v.text)}</option>`).join('');
      el.value = values.some(v => v.value === current) ? current : '';
    }

    function showBanner(kind, html) {
      const el = document.getElementById('statusBanner');
      if (!kind) { el.style.display = 'none'; return; }
      el.className = 'banner ' + (kind === 'error' ? 'banner-error' : 'banner-warn');
      el.innerHTML = html;
      el.style.display = 'block';
    }

    function showNotification(msg) {
      const el = document.getElementById('notif');
      el.textContent = msg;
      el.style.display = 'block';
      setTimeout(() => { el.style.display = 'none'; }, 4000);
    }

    function getCategoryBadgeClass(category) {
      if (category === 'potential business opportunity') return 'badge-business';
      if (category === 'potential product idea') return 'badge-product';
      if (category === 'technology worth testing') return 'badge-testing';
      if (category === 'useful technology') return 'badge-useful';
      return 'badge-interesting';
    }

    function getScoreBadgeClass(score) {
      if (score >= 75) return 'score-high';
      if (score >= 55) return 'score-med';
      if (score >= 35) return 'score-mod';
      return 'score-low';
    }

    async function getJson(url) {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`${url} returned HTTP ${res.status}`);
      return res.json();
    }

    async function loadAllData() {
      try {
        const [opps, runs, src, items] = await Promise.all([
          getJson('/api/opportunities?limit=500'),
          getJson('/api/runs'),
          getJson('/api/sources'),
          getJson('/api/items?limit=500')
        ]);
        allOpportunities = opps.opportunities || [];
        allRuns = runs.runs || [];
        allSources = src.sources || [];
        sourceSummary = src.summary || null;
        allItems = items.items || [];
        itemCounts = items.items_by_type || {};
        showBanner(null);
      } catch (err) {
        console.error('Failed to load radar data', err);
        showBanner('error', '<b>Disconnected:</b> the local Radar service did not respond (' + escapeHtml(err.message) +
          '). Figures below are from the last successful load, if any.');
        return;
      }
      const sources = [...new Set([...allOpportunities.map(o => o.source || 'GitHub'), ...allSources.filter(s => s.enabled).map(s => s.source_name)])].sort();
      const oppTypes = [...new Set(allOpportunities.map(o => o.item_type || ''))].sort();
      fillSelect('sourceFilter', sources.map(s => ({ value: s, text: s })), 'All Sources');
      fillSelect('typeFilter', oppTypes.map(t => ({ value: t, text: typeLabel(t) })), 'All Types');
      fillSelect('itemSourceFilter', [...new Set(allItems.map(i => i.source))].sort().map(s => ({ value: s, text: s })), 'All Sources');
      fillSelect('itemTypeFilter', Object.keys(itemCounts).sort().map(t => ({ value: t, text: `${typeLabel(t)} (${itemCounts[t]})` })), 'All Types');
      renderStats();
      filterFeed();
      renderItems();
      renderRuns();
      renderSources();
    }

    function runStatusPill(status) {
      const cls = status === 'success' ? 'status-success' : (status === 'partial_failure' ? 'status-partial' : 'status-failure');
      return `<span class="status-pill ${cls}">${escapeHtml(status || 'unknown')}</span>`;
    }

    function renderStats() {
      document.getElementById('statTotalOpps').textContent = allOpportunities.length;
      const topScore = allOpportunities.length ? Math.max(...allOpportunities.map(o => o.score || 0)) : 0;
      document.getElementById('statTopScore').textContent = topScore > 0 ? topScore.toFixed(1) : '-';
      if (sourceSummary) {
        document.getElementById('statSourcesCount').textContent = `${sourceSummary.configured} / ${sourceSummary.enabled}`;
        document.getElementById('statSourcesHealthy').textContent = `${sourceSummary.healthy} / ${sourceSummary.collecting}`;
      }
      if (allRuns.length > 0) {
        const last = allRuns[0];
        const date = new Date(last.started_at);
        document.getElementById('statLastRun').textContent = date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        document.getElementById('statLastRunStatus').innerHTML = runStatusPill(last.status);
        if (last.status !== 'success') {
          const failing = Object.entries(last.sources || {}).filter(([, s]) => s.status === 'failed' || s.status === 'degraded').map(([n, s]) => `${escapeHtml(n)} (${escapeHtml(s.status)})`);
          showBanner('warn', `<b>Last run: ${escapeHtml(last.status)}.</b> ` +
            (failing.length ? `Sources with errors: ${failing.join(', ')}. ` : '') +
            `${last.analysis_failed || 0} analysis failure(s). See Run History and Source Health for details.`);
        }
      } else {
        document.getElementById('statLastRun').textContent = 'Pending first run';
        document.getElementById('statLastRunStatus').innerHTML = '';
      }
    }

    function filterFeed() {
      const search = document.getElementById('searchInput').value.toLowerCase();
      const cat = document.getElementById('categoryFilter').value;
      const src = document.getElementById('sourceFilter').value;
      const type = document.getElementById('typeFilter').value;
      const minScore = parseFloat(document.getElementById('scoreFilter').value) || 0;
      const sort = document.getElementById('sortFilter').value;

      let filtered = allOpportunities.filter(item => {
        if (cat && item.category !== cat) return false;
        if (src && (item.source || 'GitHub') !== src && !(item.supporting_sources || []).some(s => s.source === src)) return false;
        if (type && (item.item_type || '') !== type) return false;
        if ((item.score || 0) < minScore) return false;
        if (search) {
          const text = (item.title + ' ' + (item.summary || '') + ' ' + (item.what_it_does || '')).toLowerCase();
          if (!text.includes(search)) return false;
        }
        return true;
      });

      if (sort === 'score') {
        filtered.sort((a, b) => (b.score || 0) - (a.score || 0));
      } else if (sort === 'newest') {
        filtered.sort((a, b) => new Date(b.date_discovered || 0) - new Date(a.date_discovered || 0));
      } else if (sort === 'verified') {
        filtered.sort((a, b) => new Date(b.last_verified || 0) - new Date(a.last_verified || 0));
      }

      const container = document.getElementById('opportunitiesContainer');
      if (filtered.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">🔍</div>
            <div class="empty-title">${allOpportunities.length ? 'No opportunities match these filters' : 'No analyzed opportunities yet'}</div>
            <div class="empty-desc">${allOpportunities.length ? 'Try relaxing the filters.' : 'Run discovery to collect and analyze items from the enabled sources.'}</div>
          </div>
        `;
        return;
      }

      container.innerHTML = filtered.map(item => {
        const score = Number(item.score || 0).toFixed(1);
        const scoreClass = getScoreBadgeClass(Number(score));
        const catBadge = getCategoryBadgeClass(item.category);
        const stars = item.github_stars != null ? `⭐ ${Number(item.github_stars).toLocaleString()} stars` : '';
        const ev = item.evidence || [];
        const evHtml = Array.isArray(ev)
          ? ev.slice(0, 4).map(e => `<span class="evidence-pill">${escapeHtml(String(e))}</span>`).join('')
          : '';

        return `
          <div class="card">
            <div class="card-header">
              <div class="card-title-area">
                <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener" class="card-title">
                  ${escapeHtml(item.title)} ↗
                </a>
                <div class="card-meta-row">
                  <span class="badge ${catBadge}">${escapeHtml(item.category || 'technology')}</span>
                  <span class="badge badge-source">${escapeHtml(item.source || 'GitHub')}</span>
                  ${item.item_type ? `<span class="badge badge-source">${escapeHtml(typeLabel(item.item_type))}</span>` : ''}
                  ${(item.supporting_sources || []).map(s => `<a class="badge badge-source" style="text-decoration:none;" href="${escapeHtml(s.url)}" target="_blank" rel="noopener">also on ${escapeHtml(s.source)} ↗</a>`).join('')}
                  ${stars ? `<span class="badge badge-source">${stars}</span>` : ''}
                  <span style="font-size: 0.8rem; color: var(--text-muted);">Confidence: <b>${escapeHtml(item.confidence || 'medium')}</b></span>
                  ${item.update_reason ? `<span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24;">⚡ Updated: ${escapeHtml(item.update_reason)}</span>` : ''}
                </div>
              </div>
              <div class="score-badge ${scoreClass}">
                <span>${score}</span>
                <span class="score-sub">RADAR SCORE</span>
              </div>
            </div>

            <div class="summary-text">${escapeHtml(item.summary || '')}</div>

            <div class="card-grid-details">
              <div class="detail-box">
                <div class="detail-label">What it does</div>
                <div class="detail-content">${escapeHtml(item.what_it_does || 'No description provided')}</div>
              </div>
              <div class="detail-box">
                <div class="detail-label">Why it matters</div>
                <div class="detail-content">${escapeHtml(item.why_it_matters || 'No rationale provided')}</div>
              </div>
              <div class="detail-box">
                <div class="detail-label">Potential use for us</div>
                <div class="detail-content">${escapeHtml(item.potential_use_for_us || 'Pending evaluation')}</div>
              </div>
            </div>

            ${item.recommended_next_action ? `
              <div class="action-box">
                <div class="action-label">Recommended Next Action</div>
                <div style="font-size: 0.875rem; color: #f1f5f9;">${escapeHtml(item.recommended_next_action)}</div>
              </div>
            ` : ''}

            <div class="card-footer">
              <div class="evidence-tags">${evHtml}</div>
              <div>Discovered: ${new Date(item.date_discovered).toLocaleDateString()} | Verified: ${item.last_verified ? new Date(item.last_verified).toLocaleDateString() : 'Yes'}</div>
            </div>
          </div>
        `;
      }).join('');
    }

    function renderItems() {
      const search = document.getElementById('itemSearch').value.toLowerCase();
      const src = document.getElementById('itemSourceFilter').value;
      const type = document.getElementById('itemTypeFilter').value;
      const rows = allItems.filter(i => (!src || i.source === src) && (!type || i.item_type === type) &&
        (!search || (i.title + ' ' + (i.description || '')).toLowerCase().includes(search)));
      const total = Object.values(itemCounts).reduce((a, b) => a + b, 0);
      document.getElementById('itemCounts').textContent =
        `${total} records indexed across sources (showing ${rows.length} of the ${allItems.length} most recent). AI analysis runs only on a small budgeted subset; jobs are indexed without analysis.`;
      const tbody = document.getElementById('itemsTableBody');
      if (rows.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color: var(--text-muted); padding: 24px;">${allItems.length ? 'No items match these filters.' : 'Nothing indexed yet. Items appear after the first multi-source discovery run.'}</td></tr>`;
        return;
      }
      const fmt = d => d ? new Date(d).toLocaleDateString() : '-';
      tbody.innerHTML = rows.map(i => {
        const ev = i.evidence || {};
        let details = [];
        if (i.item_type === 'job') {
          if (ev.employer) details.push(`Employer: ${escapeHtml(ev.employer)}`);
          if (ev.location) details.push(`Location: ${escapeHtml(ev.location)}`);
          if (ev.job_type) details.push(escapeHtml(ev.job_type.replace('_', ' ')));
          if (ev.salary) details.push(`Salary (as listed): ${escapeHtml(ev.salary)}`);
          details.push(`<a href="${escapeHtml(ev.application_url || i.url)}" target="_blank" rel="noopener">Apply via Remotive ↗</a>`);
        } else {
          if (ev.stars != null) details.push(`⭐ ${Number(ev.stars).toLocaleString()}`);
          if (ev.likes != null) details.push(`♥ ${Number(ev.likes).toLocaleString()} likes`);
          if (ev.downloads != null) details.push(`${Number(ev.downloads).toLocaleString()} downloads`);
          if (ev.points != null) details.push(`${ev.points} points, ${ev.comments || 0} comments`);
          if (ev.discussion_url) details.push(`<a href="${escapeHtml(ev.discussion_url)}" target="_blank" rel="noopener">discussion ↗</a>`);
          if (ev.publisher) details.push(escapeHtml(ev.publisher));
          if (i.author && !ev.publisher) details.push(`by ${escapeHtml(i.author)}`);
          if (i.analyzed) details.push('<span class="status-pill status-success">analyzed</span>');
        }
        (i.supporting || []).forEach(s => details.push(`<a href="${escapeHtml(s.url)}" target="_blank" rel="noopener">also on ${escapeHtml(s.source)} ↗</a>`));
        return `<tr>
          <td><a href="${escapeHtml(i.url)}" target="_blank" rel="noopener" style="color: var(--accent);">${escapeHtml(i.title)}</a></td>
          <td>${escapeHtml(typeLabel(i.item_type))}</td>
          <td>${escapeHtml(i.source)}</td>
          <td style="font-size: 0.8rem;">${details.join(' · ')}</td>
          <td>${fmt(i.published_at)}</td>
          <td style="font-size: 0.8rem;">${fmt(i.first_seen)} / ${fmt(i.last_seen)} (${i.seen_count}×)</td>
        </tr>`;
      }).join('');
    }

    function renderRuns() {
      const tbody = document.getElementById('runsTableBody');
      if (allRuns.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 24px;">No pipeline runs recorded yet.</td></tr>';
        return;
      }
      tbody.innerHTML = allRuns.map(run => {
        const dur = run.duration_seconds != null ? `${run.duration_seconds}s` : '-';
        const perSource = Object.entries(run.sources || {}).filter(([, s]) => s.status !== 'disabled')
          .map(([n, s]) => `${escapeHtml(n)}: ${escapeHtml(s.status)}${s.status === 'skipped' ? '' : ' (' + (s.collected || 0) + ')'}`).join('<br>');
        return `
          <tr>
            <td style="font-family: monospace; font-size: 0.8rem; color: var(--accent);">${escapeHtml(run.run_id)}</td>
            <td>${runStatusPill(run.status)}</td>
            <td>${new Date(run.started_at).toLocaleString()}</td>
            <td>${dur}</td>
            <td><b>${run.collected}</b></td>
            <td style="color: #34d399;">+${run.stored}</td>
            <td style="color: #fbbf24;">${run.updated || 0}</td>
            <td style="${run.failed > 0 ? 'color: #f87171;' : ''}">${run.failed}</td>
            <td style="font-size: 0.75rem;">${perSource || '-'}</td>
          </tr>
        `;
      }).join('');
    }

    function renderSources() {
      // Only real, persisted health is shown. No placeholder "ok" cards.
      const container = document.getElementById('sourcesContainer');
      if (allSources.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-title">No source information available</div><div class="empty-desc">The service returned no configured sources.</div></div>';
        return;
      }
      const pill = s => {
        if (!s.enabled) return '<span class="status-pill status-muted">DISABLED</span>';
        const cls = { ok: 'status-success', degraded: 'status-partial', failed: 'status-failure' }[s.last_status] || 'status-muted';
        return `<span class="status-pill ${cls}">${escapeHtml((s.last_status || 'unknown').replace('_', ' ').toUpperCase())}</span>`;
      };
      const when = d => d ? new Date(d).toLocaleString() : 'never';
      container.innerHTML = allSources.map(src => `
          <div class="stat-card" style="${src.enabled ? '' : 'opacity: 0.7;'}">
            <div class="stat-label">${src.configured ? 'Source Adapter' : 'Historical source (not configured)'}</div>
            <div style="font-size: 1.15rem; font-weight: 700; margin-bottom: 8px;">${escapeHtml(src.source_name)}</div>
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; gap: 8px; flex-wrap: wrap;">
              ${pill(src)}
              ${src.collecting ? '<span class="status-pill status-success">COLLECTING</span>' : ''}
            </div>
            <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 8px; line-height: 1.6;">
              ${src.enabled || src.last_run_at ? `
                Last run: ${when(src.last_run_at)} · ${src.items_collected || 0} collected${src.requests_failed ? ` · ${src.requests_failed} of ${(src.requests_ok || 0) + src.requests_failed} requests failed` : ''}<br>
                Last success: ${when(src.last_success_at)}<br>
                Indexed: <b>${src.indexed_items || 0}</b> items · ${src.opportunities || 0} analyzed opportunities` : ''}
              ${src.enabled && src.min_interval_minutes ? `<br>Polls at most every ${src.min_interval_minutes} min` : ''}
              ${!src.enabled && src.disabled_reason ? `<br>${escapeHtml(src.disabled_reason)}` : ''}
            </div>
            ${src.access ? `<div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 6px;">${escapeHtml(src.access)}</div>` : ''}
            ${src.last_error ? `<div style="color: #f87171; font-size: 0.75rem; margin-top: 8px;">Last error: ${escapeHtml(src.last_error)}</div>` : ''}
          </div>`).join('');
    }

    async function triggerDiscoveryRun() {
      const btn = document.getElementById('runBtn');
      btn.disabled = true;
      btn.textContent = '⏳ Running Discovery...';
      showNotification('Pipeline run initiated. Collecting from enabled sources and analyzing a capped number of items...');

      try {
        const res = await fetch('/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
        const data = await res.json();
        if (res.status === 409) {
          showNotification('A radar run is already in progress.');
        } else if (res.ok) {
          showNotification(`Run complete! Stored: ${data.stored}, Updated: ${data.updated || 0}, Duration: ${data.duration_seconds || 0}s`);
          await loadAllData();
        } else {
          showNotification(`Run error: ${data.error || 'Unknown error'}`);
        }
      } catch (err) {
        showNotification('Connection error while running discovery.');
      } finally {
        btn.disabled = false;
        btn.textContent = '⚡ Run Discovery Now';
      }
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    loadAllData();
  </script>
</body>
</html>
"""
