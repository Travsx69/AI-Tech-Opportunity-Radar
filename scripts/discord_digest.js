'use strict';

const MAX_DISCORD_LENGTH = 1900;
const MAX_OPPORTUNITIES = 5;

function clean(value, limit = 360) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (text.length <= limit) return text;
  return `${text.slice(0, Math.max(0, limit - 1)).trimEnd()}…`;
}

function plural(count, singular, pluralForm) {
  return count === 1 ? singular : (pluralForm || `${singular}s`);
}

function categoryEmoji(category) {
  if (category === 'potential business opportunity') return '🟣';
  if (category === 'potential product idea') return '🟠';
  if (category === 'technology worth testing' || category === 'useful technology') return '🟢';
  return '🟡';
}

function formatDate(now) {
  const date = now ? new Date(now) : new Date();
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Manila',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  }).format(date);
}

function opportunityBlock(report) {
  const source = clean(report.source, 40) || 'GitHub'; // records predating multi-source were GitHub-only
  const lines = [
    '━━━━━━━━━━━━━━━━━━',
    '',
    `${categoryEmoji(report.category)} ${clean(report.title, 120) || 'Untitled opportunity'}`,
    report.update_reason ? `🔄 Updated: ${clean(report.update_reason, 120)}` : '🆕 New',
  ];
  // Stars exist only for GitHub records; null/undefined must not render as "0 GitHub stars".
  if (report.github_stars !== null && report.github_stars !== undefined && Number.isFinite(Number(report.github_stars)) && source === 'GitHub') {
    lines.push(`⭐ ${Number(report.github_stars).toLocaleString('en-US')} GitHub stars`);
  }
  lines.push(
    '',
    'What it does:',
    clean(report.what_it_does, 340) || 'Insufficient evidence in this run.',
    '',
    'Why it matters:',
    clean(report.why_it_matters, 300) || 'Insufficient evidence in this run.',
    '',
    'Potential use for us:',
    clean(report.potential_use_for_us, 300) || 'Further review is required.',
    '',
    `🔗 ${source}:`,
    clean(report.url, 240),
  );
  const supporting = (Array.isArray(report.supporting_sources) ? report.supporting_sources : []).slice(0, 2);
  for (const s of supporting) lines.push(`↳ Also on ${clean(s.source, 40)}: ${clean(s.url, 200)}`);
  return lines.join('\n');
}

function serviceFailureDigest(now) {
  return [[
    '🤖 **AI TECH OPPORTUNITY RADAR**',
    formatDate(now),
    '',
    '⚠️ **RADAR SERVICE FAILURE**',
    '',
    'The Opportunity Radar service was unavailable or returned an invalid response.',
    'Radar discovery did not run.',
    'Collection statistics are unavailable for this execution.',
  ].join('\n')];
}

function isValidRadarResult(result) {
  return Boolean(
    result
    && typeof result === 'object'
    && !result.error
    && Number.isFinite(result.collected)
    && Number.isFinite(result.failed)
    && Array.isArray(result.reports)
  );
}

// A trigger that overlapped a run still in progress gets HTTP 409. The other run will post its own
// digest, so this execution stays silent instead of sending a false failure alert.
function isRunInProgress(result) {
  if (!result || typeof result !== 'object' || !result.error) return false;
  return /already in progress/i.test(typeof result.error === 'string' ? result.error : JSON.stringify(result.error));
}

function failingSources(result) {
  return Object.entries(result.sources || {})
    .filter(([, s]) => s && (s.status === 'failed' || s.status === 'degraded'))
    .map(([name, s]) => `${name} (${s.status})`);
}

function healthFooter(result) {
  const failing = failingSources(result);
  const analysisFailed = Number(result.analysis_failed) || 0;
  if (!failing.length && !analysisFailed) return '';
  const parts = [];
  if (failing.length) parts.push(`source errors: ${failing.join(', ')}`);
  if (analysisFailed) parts.push(`${analysisFailed} analysis ${plural(analysisFailed, 'failure')}`);
  return `⚠️ Partial failure: ${parts.join('; ')}. Details are in the Radar dashboard.`;
}

function formatDiscordDigest(result, now) {
  if (isRunInProgress(result)) return [];
  if (!isValidRadarResult(result)) return serviceFailureDigest(now);

  const reports = result.reports;
  const visible = reports.slice(0, MAX_OPPORTUNITIES);
  const count = reports.length;
  const updated = reports.filter((r) => r && r.update_reason).length;
  const fresh = count - updated;
  const footer = healthFooter(result);
  let summary = 'No new opportunities found';
  if (count > 0) {
    summary = fresh > 0
      ? `${fresh} new ${plural(fresh, 'opportunity', 'opportunities')} found${updated ? `, ${updated} materially updated` : ''}`
      : `${updated} materially updated ${plural(updated, 'opportunity', 'opportunities')}`;
  }
  const header = ['🤖 **AI TECH OPPORTUNITY RADAR**', formatDate(now), '', summary].join('\n');

  if (count === 0) {
    // Clean empty runs stay silent (no daily spam); empty runs with errors still alert.
    if (!footer && result.status !== 'failed') return [];
    return [[
      header,
      '',
      result.status === 'failed' ? '⚠️ No source could be collected in this run.' : footer,
      `Collected: ${Number(result.collected) || 0}`,
      `Failed: ${Number(result.failed) || 0}`,
    ].filter(Boolean).join('\n')];
  }

  const messages = [];
  let current = header;
  for (const report of visible) {
    const block = opportunityBlock(report);
    if (`${current}\n\n${block}`.length > MAX_DISCORD_LENGTH && current !== header) {
      messages.push(current);
      current = `🤖 **AI TECH OPPORTUNITY RADAR — CONTINUED**\n\n${block}`;
    } else {
      current = `${current}\n\n${block}`;
    }
  }
  if (reports.length > visible.length) {
    const remainder = `\n\n${reports.length - visible.length} additional ${plural(reports.length - visible.length, 'opportunity', 'opportunities')} stored in the Radar.`;
    if ((current + remainder).length <= MAX_DISCORD_LENGTH) current += remainder;
  }
  if (footer) {
    if ((`${current}\n\n${footer}`).length <= MAX_DISCORD_LENGTH) current = `${current}\n\n${footer}`;
    else { messages.push(current); current = footer; }
  }
  messages.push(current);
  return messages;
}

module.exports = { formatDiscordDigest, MAX_DISCORD_LENGTH };
