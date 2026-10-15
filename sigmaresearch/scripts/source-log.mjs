#!/usr/bin/env node
// Count a research source log: sources read in full, per meta source, language and region.
//
//   node source-log.mjs <log.md> [<log2.md> ...] [--plan "meta=10 per=10 full=100 split=china:50,west:30 must=reddit,x"] [--json]
//
// Log format (one numbered line per source; a markdown table row with the same cells works too):
//   N. meta source | URL | date | language | read=full|digest | words read | takeaway
// Rules (the same as SKILL.md "Count depth"):
//   - A source is one unique page read in full. read=digest, a snippet or a search result counts 0.
//   - The same URL twice counts once; a full line beats a digest line for the same page.
//   - The meta source comes from the URL (a platform family, else the registered domain), never from the label.
//   - At most `per` sources count per meta source; the rest are reported as over the cap.
// Exit code 1 when a plan is given and not met. No dependencies.
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

export const DEFAULT_PLAN = { meta: 10, per: 10, full: 100 };

const FAMILY = [
  ['reddit.com', 'reddit'], ['redd.it', 'reddit'], ['x.com', 'x'], ['twitter.com', 'x'], ['t.co', 'x'],
  ['youtube.com', 'youtube'], ['youtu.be', 'youtube'], ['bilibili.com', 'bilibili'], ['b23.tv', 'bilibili'],
  ['weibo.com', 'weibo'], ['weibo.cn', 'weibo'], ['zhihu.com', 'zhihu'], ['baike.baidu.com', 'baidu baike'],
  ['baidu.com', 'baidu'], ['douyin.com', 'douyin'], ['xiaohongshu.com', 'xiaohongshu'], ['news.cn', 'xinhua'],
  ['xinhuanet.com', 'xinhua'], ['wikipedia.org', 'wikipedia'], ['google.com', 'google'], ['facebook.com', 'facebook'],
  ['tiktok.com', 'tiktok'], ['github.com', 'github'], ['huggingface.co', 'huggingface'],
  ['news.ycombinator.com', 'hacker news'], ['rumble.com', 'rumble'], ['instagram.com', 'instagram'],
];
const CHINA_META = new Set(['bilibili', 'weibo', 'zhihu', 'baidu baike', 'baidu', 'douyin', 'xiaohongshu', 'xinhua']);
const SECOND_LEVEL = new Set(['com', 'co', 'org', 'net', 'gov', 'edu', 'ac']);
const LANG_NAMES = { english: 'en', chinese: 'zh', mandarin: 'zh', serbian: 'sr', german: 'de', russian: 'ru', japanese: 'ja' };
const TRACKING = /^(utm_|fbclid|gclid|ref$|ref_src|si$|feature$|share|spm$|from$|s$|t$)/i;
const URL_RE = /https?:\/\/[^\s|)>\]]+/;

export function hostOf(url) {
  try {
    return new URL(url).hostname.toLowerCase().replace(/^(www|m|mobile|old|new|i|en|zh|amp)\./, '');
  } catch {
    return '';
  }
}

export function metaOf(url, label = '') {
  const host = hostOf(url);
  for (const [suffix, family] of FAMILY) if (host === suffix || host.endsWith(`.${suffix}`)) return family;
  if (!host) return label.replace(/\s*\(.*?\)/g, '').trim().toLowerCase() || 'unknown';
  const parts = host.split('.');
  const n = parts.length >= 3 && SECOND_LEVEL.has(parts[parts.length - 2]) && parts[parts.length - 1].length === 2 ? 3 : 2;
  return parts.slice(-n).join('.');
}

export function keyOf(url) {
  let u;
  try {
    u = new URL(url.trim().replace(/[.,;]+$/, ''));
  } catch {
    return url.trim();
  }
  const host = hostOf(url);
  const path = u.pathname.replace(/\/+$/, '') || '/';
  const query = [...u.searchParams].filter(([k]) => !TRACKING.test(k)).sort(([a], [b]) => a.localeCompare(b));
  const meta = metaOf(url);
  let m;
  if (meta === 'reddit' && (m = path.match(/\/comments\/(\w+)/))) return `reddit/comments/${m[1]}`;
  if (meta === 'youtube') {
    const v = u.searchParams.get('v') || (host === 'youtu.be' ? path.slice(1) : (path.match(/\/(?:shorts|embed|live)\/([\w-]+)/) || [])[1]);
    if (v) return `youtube/${v}`;
  }
  if (meta === 'x' && (m = path.match(/\/status\/(\d+)/))) return `x/status/${m[1]}`;
  return host + path + (query.length ? `?${query.map(([k, v]) => `${k}=${v}`).join('&')}` : '');
}

export function regionOf(url, lang, explicit = '') {
  if (explicit) return explicit.toLowerCase();
  const host = hostOf(url);
  if (/^zh(-|$)/.test(lang) || CHINA_META.has(metaOf(url)) || host.endsWith('.cn')) return 'china';
  if (['sr', 'hr', 'bs', 'sh'].includes(lang) || /^sr-/.test(lang) || host.endsWith('.rs')) return 'serbia';
  return 'west';
}

// One source line -> a row, or null. Cells are read by what they hold, not by column.
export function parseLine(line) {
  const s = line.trim();
  if (!s || /^[#>]/.test(s) || !s.includes('|') || !URL_RE.test(s)) return null;
  const url = s.match(URL_RE)[0].replace(/[.,;]+$/, '');
  const cells = s.replace(/^\s*(?:\d+[.)]|-)\s*/, '').replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());
  const at = cells.findIndex((c) => URL_RE.test(c));
  const before = cells.slice(0, at);
  const after = cells.slice(at + 1);
  const label = before.find((c) => c && !/^\d+$/.test(c)) || '';
  let read = null;
  for (const c of after) {
    const r = c.match(/^read\s*=\s*(full|digest)$/i);
    if (r) read = r[1].toLowerCase();
    else if (/^[FRSD]$/.test(c) && read === null) read = 'FRS'.includes(c) ? 'full' : 'digest'; // old Tag column: F, R, S full; D digest
  }
  const date = after.find((c) => /^(\d{4}-\d{2}(-\d{2})?|unknown|n\/a|\?)$/i.test(c)) || '';
  const langCell = after.find((c) => /^([a-z]{2,3}(-[A-Za-z]+)?|english|chinese|mandarin|serbian|german|russian|japanese)$/.test(c));
  const lang = langCell ? (LANG_NAMES[langCell.toLowerCase()] || langCell.toLowerCase()) : '?';
  const wordsCell = after.find((c) => /^\d[\d,]*$/.test(c));
  const regionCell = after.map((c) => c.match(/^region\s*=\s*([\w-]+)$/i)).find(Boolean);
  return {
    url, key: keyOf(url), meta: metaOf(url, label), label, date, lang,
    read: read || 'digest', words: wordsCell ? Number(wordsCell.replace(/,/g, '')) : null,
    region: regionOf(url, lang, regionCell ? regionCell[1] : ''),
  };
}

export function parseLog(text) {
  return text.split(/\r?\n/).map(parseLine).filter(Boolean);
}

// Plan words: "meta=10 per=10 full=100 split=china:50,west:30 must=reddit,x". Missing words = the default.
export function parsePlan(words = '') {
  const plan = { ...DEFAULT_PLAN };
  const w = Object.fromEntries([...String(words).matchAll(/(?<![\w-])([a-z][\w-]*)\s*=\s*(\S+)/gi)].map((m) => [m[1].toLowerCase(), m[2].replace(/[,.;:]+$/, '')]));
  for (const k of ['meta', 'per', 'full', 'rounds', 'agents']) if (/^\d+$/.test(w[k] || '')) plan[k] = Number(w[k]);
  if (w.split) plan.split = Object.fromEntries([...w.split.matchAll(/([a-z-]+):(\d+)/gi)].map((m) => [m[1].toLowerCase(), Number(m[2])]));
  if (w.must) plan.must = w.must.split(/[,+]/).filter(Boolean).map((x) => x.toLowerCase());
  return plan;
}

// Count rows from one or more logs (rows in log order): unique pages, a full line beats a digest line.
export function tally(rows, plan = DEFAULT_PLAN) {
  const unique = new Map();
  for (const r of rows) {
    const old = unique.get(r.key);
    if (!old || (old.read === 'digest' && r.read === 'full')) unique.set(r.key, r);
  }
  const byMeta = {};
  for (const r of unique.values()) {
    byMeta[r.meta] ??= { full: 0, digest: 0, counted: 0 };
    byMeta[r.meta][r.read] += 1;
  }
  const counted = [];
  const seen = {};
  for (const r of unique.values()) {
    if (r.read !== 'full') continue;
    seen[r.meta] = (seen[r.meta] || 0) + 1;
    if (seen[r.meta] <= plan.per) counted.push(r);
  }
  const over = {};
  for (const [m, c] of Object.entries(byMeta)) {
    c.counted = Math.min(c.full, plan.per);
    if (c.full > plan.per) over[m] = c.full - plan.per;
  }
  const tallyOf = (f) => counted.reduce((a, r) => ({ ...a, [r[f]]: (a[r[f]] || 0) + 1 }), {});
  return {
    lines: rows.length, unique: unique.size, counted: counted.length,
    full: [...unique.values()].filter((r) => r.read === 'full').length,
    digest: [...unique.values()].filter((r) => r.read === 'digest').length,
    metasFull: Object.values(byMeta).filter((c) => c.counted > 0).length,
    byMeta, over, lang: tallyOf('lang'), region: tallyOf('region'),
  };
}

// The plan against the tally -> problem lines ([] = met).
export function check(t, plan = DEFAULT_PLAN) {
  const out = [];
  if (t.counted < plan.full) out.push(`${t.counted} sources read in full, plan ${plan.full} (meta=${plan.meta} per=${plan.per}); ${t.digest} digest lines count 0`);
  if (t.metasFull < plan.meta) out.push(`${t.metasFull} meta sources with a full read, plan ${plan.meta}`);
  for (const [region, need] of Object.entries(plan.split || {})) {
    const got = t.region[region] || 0;
    if (got < need) out.push(`region ${region} has ${got} full sources, plan ${need}`);
  }
  for (const m of plan.must || []) if (!t.byMeta[m]?.full) out.push(`mandatory meta source '${m}' has no source read in full`);
  return out;
}

function main(argv) {
  const files = argv.filter((a, i) => !a.startsWith('--') && !['--plan'].includes(argv[i - 1]));
  const planAt = argv.indexOf('--plan');
  if (!files.length) {
    console.error('usage: node source-log.mjs <log.md>... [--plan "meta=10 per=10 full=100"] [--json]');
    return 2;
  }
  const plan = parsePlan(planAt >= 0 ? argv[planAt + 1] : '');
  const t = tally(files.flatMap((f) => parseLog(readFileSync(f, 'utf8'))), plan);
  const problems = planAt >= 0 ? check(t, plan) : [];
  if (argv.includes('--json')) {
    console.log(JSON.stringify({ ...t, problems }, null, 2));
  } else {
    console.log(`${t.lines} source lines, ${t.unique} unique pages; counted ${t.counted} read in full (plan ${plan.full}), ${t.metasFull} meta sources, ${t.digest} digests (0)`);
    for (const [m, c] of Object.entries(t.byMeta).filter(([, c]) => c.full).sort((a, b) => b[1].counted - a[1].counted)) console.log(`  ${m}: ${c.counted} counted (${c.full} full, ${c.digest} digest)`);
    console.log(`language: ${JSON.stringify(t.lang)}  region: ${JSON.stringify(t.region)}`);
    for (const [m, n] of Object.entries(t.over)) console.log(`over the cap, not counted: ${m} +${n}`);
    for (const p of problems) console.log(`SHORT ${p}`);
  }
  return problems.length ? 1 : 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) process.exit(main(process.argv.slice(2)));
