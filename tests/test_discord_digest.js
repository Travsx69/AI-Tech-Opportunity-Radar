const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { formatDiscordDigest } = require('../scripts/discord_digest');

function runWorkflowFormatter(input) {
  const workflowPath = path.join(__dirname, '..', 'workflows', 'github-mvp.n8n.json');
  const workflow = JSON.parse(fs.readFileSync(workflowPath, 'utf8'));
  const code = workflow.nodes.find((node) => node.name === 'Format Discord Digest').parameters.jsCode;
  return vm.runInNewContext(`(function () { ${code} })()`, {
    $input: { first: () => ({ json: input }) },
    Intl,
    Date,
  });
}

test('formats one evidence-grounded opportunity', () => {
  const messages = formatDiscordDigest({
    collected: 20,
    stored: 1,
    failed: 0,
    reports: [{
      title: 'microsoft/playwright-mcp',
      category: 'technology worth testing',
      github_stars: 31626,
      what_it_does: 'The repository description claims it exposes browser automation through MCP.',
      why_it_matters: 'It aligns with computer-use and agent development.',
      potential_use_for_us: 'Test it in a small browser-agent prototype.',
      url: 'https://github.com/microsoft/playwright-mcp',
    }],
  }, '2026-09-23T00:00:00+08:00');

  assert.equal(messages.length, 1);
  assert.match(messages[0], /AI TECH OPPORTUNITY RADAR/);
  assert.match(messages[0], /September 23, 2026/);
  assert.match(messages[0], /1 new opportunity found/);
  assert.match(messages[0], /31,626 GitHub stars/);
  assert.match(messages[0], /What it does:/);
  assert.match(messages[0], /https:\/\/github.com\/microsoft\/playwright-mcp/);
  assert.ok(messages[0].length <= 1900);
});

test('a clean run with nothing new sends no message (no daily spam)', () => {
  const messages = formatDiscordDigest({ collected: 20, stored: 0, failed: 0, status: 'success', reports: [] }, '2026-09-23T00:00:00+08:00');

  assert.deepEqual(messages, []);
});

test('an empty run with source errors still alerts, naming the failing sources', () => {
  const messages = formatDiscordDigest({
    collected: 20, stored: 0, failed: 1, status: 'partial_failure', reports: [],
    sources: { GitHub: { status: 'ok' }, 'RSS/Atom Feeds': { status: 'degraded' }, Remotive: { status: 'skipped' } },
  }, '2026-09-23T00:00:00+08:00');

  assert.equal(messages.length, 1);
  assert.match(messages[0], /No new opportunities found/);
  assert.match(messages[0], /RSS\/Atom Feeds \(degraded\)/);
  assert.doesNotMatch(messages[0], /Remotive/);
  assert.match(messages[0], /Collected: 20/);
});

test('an overlapping trigger rejected with 409 stays silent instead of alerting', () => {
  const messages = formatDiscordDigest({
    error: { message: '409 - "{\\"error\\": \\"a radar run is already in progress\\"}"' },
  }, '2026-09-23T00:00:00+08:00');

  assert.deepEqual(messages, []);
});

test('non-GitHub reports use their own source label, no star line, and show attribution', () => {
  const messages = formatDiscordDigest({
    collected: 5, stored: 1, failed: 0, status: 'success',
    reports: [{
      title: 'Show HN: Agent runner', source: 'Hacker News', github_stars: null, category: 'potential product idea',
      what_it_does: 'The post claims it runs agents.', why_it_matters: 'x', potential_use_for_us: 'y',
      url: 'https://example.com/agent',
      supporting_sources: [{ source: 'RSS/Atom Feeds', url: 'https://news.example.com/agent' }],
    }, {
      title: 'acme/tool', source: 'GitHub', github_stars: 10, update_reason: 'Stars increased from 2 to 10',
      what_it_does: 'a', why_it_matters: 'b', potential_use_for_us: 'c', url: 'https://github.com/acme/tool',
    }],
  }, '2026-09-23T00:00:00+08:00');

  const text = messages.join('\n');
  assert.match(text, /🔗 Hacker News:/);
  assert.doesNotMatch(text, /\b0 GitHub stars/);
  assert.match(text, /🆕 New/);
  assert.match(text, /Also on RSS\/Atom Feeds: https:\/\/news.example.com\/agent/);
  assert.match(text, /🔄 Updated: Stars increased from 2 to 10/);
  assert.match(text, /10 GitHub stars/);
});

test('partial failure footer accompanies a digest with reports', () => {
  const messages = formatDiscordDigest({
    collected: 5, stored: 1, failed: 2, analysis_failed: 1, status: 'partial_failure',
    sources: { 'Hugging Face': { status: 'failed' } },
    reports: [{ title: 'x', source: 'GitHub', github_stars: 1, url: 'https://github.com/a/x' }],
  }, '2026-09-23T00:00:00+08:00');

  assert.match(messages.join('\n'), /Partial failure: source errors: Hugging Face \(failed\); 1 analysis failure/);
});

test('workflow Code node is generated from scripts/discord_digest.js', () => {
  const workflow = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'workflows', 'github-mvp.n8n.json'), 'utf8'));
  const code = workflow.nodes.find((node) => node.name === 'Format Discord Digest').parameters.jsCode;
  const script = fs.readFileSync(path.join(__dirname, '..', 'scripts', 'discord_digest.js'), 'utf8').split('module.exports')[0].trimEnd();
  assert.ok(code.startsWith(script), 'run: python scripts/sync_workflow_code.py');
  assert.equal(runWorkflowFormatter({ collected: 1, failed: 0, status: 'success', reports: [] }).length, 0);
});

test('workflow keeps the deployed 6 AM Asia/Manila schedule and Discord credential', () => {
  const workflow = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'workflows', 'github-mvp.n8n.json'), 'utf8'));
  const schedule = workflow.nodes.find((node) => node.type === 'n8n-nodes-base.scheduleTrigger');
  assert.equal(schedule.parameters.rule.interval[0].expression, '0 6 * * *');
  assert.equal(workflow.settings.timezone, 'Asia/Manila');
  const http = workflow.nodes.find((node) => node.type === 'n8n-nodes-base.httpRequest');
  assert.equal(http.continueOnFail, true);
  assert.equal(http.parameters.url, 'http://host.docker.internal:8787/run');
  const discord = workflow.nodes.find((node) => node.type === 'n8n-nodes-base.discord');
  assert.equal(discord.credentials.discordWebhookApi.id, '4xCiRHtIT9ZbnuFr');
});

test('reports an unavailable Radar service without inventing zero statistics', () => {
  const messages = formatDiscordDigest({
    error: {
      message: 'connect ECONNREFUSED 192.168.65.254:8787',
    },
  }, '2026-09-23T00:00:00+08:00');

  assert.equal(messages.length, 1);
  assert.match(messages[0], /RADAR SERVICE FAILURE/);
  assert.match(messages[0], /Opportunity Radar service was unavailable/);
  assert.match(messages[0], /Radar discovery did not run/);
  assert.doesNotMatch(messages[0], /No new opportunities found/);
  assert.doesNotMatch(messages[0], /Collected: 0/);
  assert.doesNotMatch(messages[0], /Failed: 0/);
});

test('treats a malformed upstream response as a service failure', () => {
  const messages = formatDiscordDigest({}, '2026-09-23T00:00:00+08:00');

  assert.equal(messages.length, 1);
  assert.match(messages[0], /RADAR SERVICE FAILURE/);
  assert.match(messages[0], /Radar discovery did not run/);
  assert.doesNotMatch(messages[0], /Collected: 0/);
});

test('n8n workflow formatter reports a failed HTTP request as a service failure', () => {
  const items = runWorkflowFormatter({
    error: { message: 'connect ECONNREFUSED 192.168.65.254:8787' },
  });

  assert.equal(items.length, 1);
  assert.match(items[0].json.content, /RADAR SERVICE FAILURE/);
  assert.match(items[0].json.content, /Radar discovery did not run/);
  assert.doesNotMatch(items[0].json.content, /Collected: 0/);
});

test('splits multiple reports into Discord-safe messages', () => {
  const longText = 'Evidence-grounded explanation '.repeat(30);
  const reports = Array.from({ length: 5 }, (_, index) => ({
    title: `owner/tool-${index + 1}`,
    category: 'useful technology',
    github_stars: 1000 + index,
    what_it_does: longText,
    why_it_matters: longText,
    potential_use_for_us: longText,
    url: `https://github.com/owner/tool-${index + 1}`,
  }));

  const messages = formatDiscordDigest({ collected: 20, stored: 5, failed: 0, reports }, '2026-09-23T00:00:00+08:00');

  assert.ok(messages.length > 1);
  assert.ok(messages.every((message) => message.length <= 1900));
  assert.match(messages.join('\n'), /owner\/tool-5/);
});
