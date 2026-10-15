import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

function findPython() {
  for (const cmd of ['python3', 'python', 'py']) {
    const r = spawnSync(cmd, ['--version'], { encoding: 'utf8' });
    if (r.status === 0 && /Python 3\.(\d+)/.test(r.stdout + r.stderr)) return cmd;
  }
  return null;
}

// The sigmaresearch readers are Python stdlib scripts. Their unit tests run on recorded fixtures, no network.
test('sigmaresearch reader unit tests pass (python unittest, offline)', (t) => {
  const python = findPython();
  if (!python) return t.skip('python 3 not found');
  const r = spawnSync(python, ['-m', 'unittest', 'discover', '-s', 'test/sigmaresearch', '-v'], {
    cwd: root,
    encoding: 'utf8',
    env: { ...process.env, SIGMARESEARCH_LIVE: '', PYTHONDONTWRITEBYTECODE: '1' },
  });
  assert.equal(r.status, 0, (r.stdout || '') + (r.stderr || ''));
});

// ---- counting and source-log parsing (scripts/source_log.py: reads files only, no network) ----

const SOURCE_LOG = join(root, 'sigmaresearch', 'scripts', 'source_log.py');

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

// Write each log to a temp file, run the counter with --json, return { status, out, stderr }; null when python 3 is missing.
function count(t, logs, ...args) {
  const python = findPython();
  if (!python) {
    t.skip('python 3 not found');
    return null;
  }
  const dir = mkdtempSync(join(tmpdir(), 'sigmaresearch-'));
  try {
    const files = logs.map((text, i) => {
      const file = join(dir, `${'abc'[i]}-sources.md`);
      writeFileSync(file, text);
      return file;
    });
    const r = spawnSync(python, [SOURCE_LOG, ...files, '--json', ...args], {
      encoding: 'utf8',
      env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
    });
    return { status: r.status, out: JSON.parse(r.stdout || '{}'), stderr: r.stderr };
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

test('source log: the same page counts once, a digest counts 0, meta comes from the URL', (t) => {
  const r = count(t, [LOG]);
  if (!r) return;
  assert.equal(r.status, 0, r.stderr);
  assert.equal(r.out.lines, 8);
  assert.equal(r.out.unique, 6, 'old.reddit and www.reddit threads, youtu.be and watch?v= are one page each');
  assert.equal(r.out.counted, 5);
  assert.equal(r.out.digest, 1);
  assert.deepEqual(r.out.by_meta.reddit, { full: 1, digest: 1, counted: 1 });
  assert.equal(r.out.by_meta.youtube.full, 1);
  assert.equal(r.out.by_meta.xinhua.full, 1, 'the label and the news.cn host agree; a tracking param is no new page');
  assert.equal(r.out.by_meta['tanjug.rs'].full, 1, 'an unknown site is its registered domain, not the label');
  assert.equal(r.out.metas_full, 5);
});

test('source log: a full line beats a digest line for the same page, across files', (t) => {
  const digest = '1. Reddit | https://www.reddit.com/r/a/comments/zzz/ | 2026-10-14 | en | read=digest | 10 | snippet\n';
  const full = '1. Reddit | https://www.reddit.com/r/a/comments/zzz/ | 2026-10-14 | en | read=full | 900 | later read in full\n';
  const r = count(t, [digest, full]);
  if (!r) return;
  assert.deepEqual(r.out.by_meta.reddit, { full: 1, digest: 0, counted: 1 });
});

test('source log: at most per sources count per meta source; language and region follow the counted ones', (t) => {
  const lines = Array.from({ length: 14 }, (_, i) => `${i + 1}. Reddit | https://www.reddit.com/r/a/comments/id${i}/ | 2026-10-14 | en | read=full | 500 | t`);
  lines.push('15. Bilibili | https://www.bilibili.com/video/BV1x | 2026-10-10 | zh | read=full | 900 | t');
  const r = count(t, [lines.join('\n')]);
  if (!r) return;
  assert.equal(r.out.by_meta.reddit.full, 14);
  assert.equal(r.out.by_meta.reddit.counted, 10);
  assert.deepEqual(r.out.over, { reddit: 4 });
  assert.equal(r.out.counted, 11);
  assert.deepEqual(r.out.region, { west: 10, china: 1 });
  assert.deepEqual(r.out.lang, { en: 10, zh: 1 });
});

test('source log: pages of one site differ by path or id, not by tracking or trailing slash', (t) => {
  const log = [
    '1. Blog | https://example.com/a?id=1 | 2026-10-01 | en | read=full | 500 | t',
    '2. Blog | https://example.com/a?id=2 | 2026-10-01 | en | read=full | 500 | t',
    '3. Blog | https://www.example.com/a/?id=2&utm_source=x#top | 2026-10-01 | en | read=full | 500 | t',
  ].join('\n');
  const r = count(t, [log]);
  if (!r) return;
  assert.equal(r.out.unique, 2);
  assert.equal(r.out.by_meta['example.com'].full, 2);
});

test('source log parsing: table rows, an old Tag column, a missing read word, headers and prose', (t) => {
  const old = count(t, [OLD_TAG_LOG]);
  if (!old) return;
  assert.equal(old.out.counted, 2, 'F and R are full');
  assert.equal(old.out.digest, 1, 'D is a digest');
  const mixed = count(t, [[
    '| 3 | Reddit | https://www.reddit.com/r/a/comments/q/ | 2026-10-14 | en | read=digest | 10 | snippet |',
    '1. Blog | https://example.com/a | 2026-10-01 | en | | 500 | no read word',
    '| # | Meta | URL | Date |',
    'A prose line with a link https://example.com/prose but no cells.',
    '# agent A',
  ].join('\n')]);
  assert.equal(mixed.out.lines, 2, 'only the two source lines parse');
  assert.equal(mixed.out.counted, 0, 'no read word counts as a digest');
  assert.equal(mixed.out.digest, 2);
});

test('source log: plan words bind only when given; default 100; split and must are enforced', (t) => {
  const none = count(t, [LOG], '--plan', '');
  if (!none) return;
  assert.equal(none.status, 1, 'no plan words = the default 100');
  assert.ok(none.out.problems.some((p) => p.includes('5 sources read in full, plan 100')));
  const met = count(t, [LOG], '--plan', 'meta=3 per=2 full=4');
  assert.equal(met.status, 0, met.out.problems.join('; '));
  const split = count(t, [LOG], '--plan', 'meta=2 per=10 full=3 split=china:5 must=x');
  assert.equal(split.status, 1);
  assert.ok(split.out.problems.some((p) => p.includes('region china has 2')));
  assert.ok(split.out.problems.some((p) => p.includes("'x' has no source")));
  assert.ok(!split.out.problems.some((p) => p.includes('read in full, plan')), 'full=3 is met by 5 counted');
  assert.equal(count(t, [LOG]).status, 0, 'without --plan the script only counts');
});

test('SKILL.md carries the ladder, the counting rules and the log contract', () => {
  const skill = readFileSync(join(root, 'sigmaresearch', 'SKILL.md'), 'utf8');
  for (const must of [/read in full/i, /meta source/i, /ladder/i, /read=full\|digest/, /scripts\/source_log\.py/]) assert.match(skill, must);
  for (const rel of ['access-ladder.md', 'counting.md']) {
    assert.ok(existsSync(join(root, 'sigmaresearch', 'references', rel)), `missing references/${rel}`);
    assert.ok(skill.includes(`references/${rel}`), `SKILL.md must link references/${rel}`);
  }
  assert.match(readFileSync(join(root, 'sigmaresearch', 'references', 'counting.md'), 'utf8'), /python scripts\/source_log\.py/);
});
