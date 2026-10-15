import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import { check, keyOf, metaOf, parseLine, parseLog, parsePlan, regionOf, tally } from '../sigmaresearch/scripts/source-log.mjs';

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const SCRIPT = path.join(ROOT, 'sigmaresearch', 'scripts', 'source-log.mjs');

// The same fixture the StorgeStudio kit tests use: both counters must give the same numbers.
const LOG = `# agent A
1. Reddit | https://www.reddit.com/r/energy/comments/1x5csut/title/ | 2026-10-14 | en | read=full | 1757 | post + 95 comments
2. Reddit | https://old.reddit.com/r/energy/comments/1x5csut/ | 2026-10-14 | en | read=full | 1757 | same thread again
3. Reddit | https://www.reddit.com/r/solar/comments/1wnwnxj/ | 2026-09-23 | en | read=digest | 40 | search snippet only
4. Xinhua | https://www.news.cn/auto/20261008/1a53/c.html?utm_source=x | 2026-10-08 | zh | read=full | 881 | FAW Toyota GAC deal
5. YouTube | https://youtu.be/abc123XYZ00 | 2026-10-01 | en | read=full | 4200 | subtitles
6. YouTube | https://www.youtube.com/watch?v=abc123XYZ00&t=30 | 2026-10-01 | en | read=full | 4200 | same video
7. Bilibili | https://www.bilibili.com/video/BV1KYJk6JEDk | 2026-10-10 | zh | read=full | 83 | whisper
8. Tanjug | https://www.tanjug.rs/story/1 | 2026-10-09 | sr | read=full | 600 | Sabac
`;

const OLD_TAG_LOG = `| # | Meta source | Title | URL | Date | Tag | One-line takeaway |
|---|---|---|---|---|---|---|
| 1 | Reddit r/energy | A | https://www.reddit.com/r/energy/comments/aaa111/ | 2026-10-14 | R | x |
| 2 | Ember | B | https://ember-energy.org/data/1 | 2026-09-01 | F | x |
| 3 | Search | C | https://example.com/c | 2026-09-01 | D | digest only |
`;

test('meta source comes from the URL family, never from the label', () => {
  assert.equal(metaOf('https://old.reddit.com/r/x/comments/1/'), 'reddit');
  assert.equal(metaOf('https://zh.wikipedia.org/wiki/x'), 'wikipedia');
  assert.equal(metaOf('https://energy.people.com.cn/n1/a.html'), 'people.com.cn');
  assert.equal(metaOf('https://www.bbc.co.uk/news/1'), 'bbc.co.uk');
  assert.equal(metaOf('', 'Reddit r/energy (RSS)'), 'reddit r/energy');
});

test('one page is one key: threads, videos and posts by id, no tracking', () => {
  assert.equal(keyOf('https://www.reddit.com/r/a/comments/zzz/slug/'), keyOf('https://old.reddit.com/r/b/comments/zzz/'));
  assert.equal(keyOf('https://youtu.be/abc'), keyOf('https://www.youtube.com/watch?v=abc&t=9'));
  assert.equal(keyOf('https://x.com/u/status/123?s=20'), 'x/status/123');
  assert.equal(keyOf('https://example.com/a/?utm_source=z#top'), keyOf('http://www.example.com/a'));
  assert.notEqual(keyOf('https://example.com/a?id=1'), keyOf('https://example.com/a?id=2'));
});

test('a line parses by cell content: new contract, table row and old Tag column', () => {
  const row = parseLine('12. Xinhua | https://www.news.cn/a/c.html | 2026-10-08 | zh | read=full | 881 | FAW deal');
  assert.deepEqual([row.meta, row.date, row.lang, row.read, row.words, row.region], ['xinhua', '2026-10-08', 'zh', 'full', 881, 'china']);
  const table = parseLine('| 3 | Reddit | https://www.reddit.com/r/a/comments/q/ | 2026-10-14 | en | read=digest | 10 | snippet |');
  assert.deepEqual([table.meta, table.read, table.words], ['reddit', 'digest', 10]);
  assert.equal(parseLine('| # | Meta | URL | Date |'), null, 'a header row has no URL');
  assert.equal(parseLine('# agent A'), null);
  assert.equal(parseLine('3. a line with a URL https://example.com but no pipe'), null, 'a line with no pipe is no source');
});

test('a source with no read word counts as a digest (0)', () => {
  const t = tally([parseLine('1. Blog | https://example.com/a | 2026-10-01 | en | | 500 | no read word')]);
  assert.equal(t.counted, 0);
  assert.equal(t.digest, 1);
});

test('the same page counts once, a digest counts 0, a full line beats a digest line', () => {
  const t = tally(parseLog(LOG));
  assert.equal(t.unique, 6);
  assert.equal(t.counted, 5);
  assert.equal(t.digest, 1);
  assert.deepEqual(t.byMeta.reddit, { full: 1, digest: 1, counted: 1 });
  assert.equal(t.byMeta.youtube.full, 1);
  const upgraded = tally(parseLog(
    '1. Reddit | https://www.reddit.com/r/a/comments/zzz/ | 2026-10-14 | en | read=digest | 10 | snippet\n' +
    '2. Reddit | https://www.reddit.com/r/a/comments/zzz/ | 2026-10-14 | en | read=full | 900 | later read in full\n'));
  assert.deepEqual(upgraded.byMeta.reddit, { full: 1, digest: 0, counted: 1 });
});

test('at most per sources count per meta source; the rest are over the cap', () => {
  const lines = Array.from({ length: 14 }, (_, i) => `${i + 1}. Reddit | https://www.reddit.com/r/a/comments/id${i}/ | 2026-10-14 | en | read=full | 500 | t`);
  lines.push('15. Bilibili | https://www.bilibili.com/video/BV1x | 2026-10-10 | zh | read=full | 900 | t');
  const t = tally(parseLog(lines.join('\n')), { meta: 10, per: 10, full: 100 });
  assert.equal(t.byMeta.reddit.counted, 10);
  assert.deepEqual(t.over, { reddit: 4 });
  assert.equal(t.counted, 11);
  assert.deepEqual(t.region, { west: 10, china: 1 });
  assert.deepEqual(t.lang, { en: 10, zh: 1 });
});

test('an old log with a Tag column reads F, R, S as full and D as digest', () => {
  const t = tally(parseLog(OLD_TAG_LOG));
  assert.equal(t.counted, 2);
  assert.equal(t.digest, 1);
});

test('plan words: default 100, split and must are read, only logged words bind', () => {
  assert.deepEqual(parsePlan(''), { meta: 10, per: 10, full: 100 });
  const plan = parsePlan('meta=10 per=10 full=100 rounds=2 agents=2 split=china:50,serbia:20,west:30 must=reddit,x.');
  assert.deepEqual(plan.split, { china: 50, serbia: 20, west: 30 });
  assert.deepEqual(plan.must, ['reddit', 'x']);
  const t = tally(parseLog(LOG), plan);
  const problems = check(t, parsePlan('meta=2 per=10 full=3 split=china:5 must=x'));
  assert.ok(problems.some((p) => p.includes('region china has 2')));
  assert.ok(problems.some((p) => p.includes("'x' has no source")));
  assert.ok(!problems.some((p) => p.includes('read in full, plan')), 'full=3 is met by 5 counted');
  assert.ok(check(t).some((p) => p.includes('5 sources read in full, plan 100')), 'no word = the default 100');
});

test('regions follow the language and the site, or an explicit cell', () => {
  assert.equal(regionOf('https://example.com/a', 'zh'), 'china');
  assert.equal(regionOf('https://www.zhihu.com/q/1', 'en'), 'china');
  assert.equal(regionOf('https://n1info.rs/x', 'en'), 'serbia');
  assert.equal(regionOf('https://example.com/a', 'en'), 'west');
  assert.equal(regionOf('https://example.com/a', 'en', 'Africa'), 'africa');
});

test('the command line counts a log file and exits 1 when the plan is not met', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigmaresearch-'));
  try {
    const file = path.join(dir, 'a-sources.md');
    fs.writeFileSync(file, LOG);
    const run = (...args) => spawnSync(process.execPath, [SCRIPT, file, ...args], { encoding: 'utf8' });
    const plain = run();
    assert.equal(plain.status, 0, plain.stderr);
    assert.match(plain.stdout, /counted 5 read in full/);
    const short = run('--plan', 'full=100');
    assert.equal(short.status, 1);
    assert.match(short.stdout, /SHORT 5 sources read in full, plan 100/);
    const met = run('--plan', 'meta=3 per=2 full=4', '--json');
    assert.equal(met.status, 0, met.stdout);
    assert.deepEqual(JSON.parse(met.stdout).problems, []);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('SKILL.md carries the ladder, the counting rules and the log contract', () => {
  const skill = fs.readFileSync(path.join(ROOT, 'sigmaresearch', 'SKILL.md'), 'utf8');
  for (const must of [/read in full/i, /meta source/i, /ladder/i, /read=full\|digest/, /scripts\/source-log\.mjs/]) assert.match(skill, must);
  for (const rel of ['access-ladder.md', 'counting.md']) {
    assert.ok(fs.existsSync(path.join(ROOT, 'sigmaresearch', 'references', rel)), `missing references/${rel}`);
    assert.ok(skill.includes(`references/${rel}`), `SKILL.md must link references/${rel}`);
  }
});
