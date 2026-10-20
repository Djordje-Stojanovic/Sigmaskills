import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const script = join(root, 'sigmahuman', 'scripts', 'factcheck.py');

function findPython() {
  for (const cmd of ['python3', 'python', 'py']) {
    const r = spawnSync(cmd, ['--version'], { encoding: 'utf8' });
    if (r.status === 0 && /Python 3\.(\d+)/.test(r.stdout + r.stderr)) return cmd;
  }
  return null;
}

function factcheck(python, before, after) {
  const dir = mkdtempSync(join(tmpdir(), 'sigmahuman-'));
  try {
    writeFileSync(join(dir, 'before.txt'), before);
    writeFileSync(join(dir, 'after.txt'), after);
    const r = spawnSync(python, ['-I', script, join(dir, 'before.txt'), join(dir, 'after.txt'), '--json'], { encoding: 'utf8' });
    return { status: r.status, report: r.stdout ? JSON.parse(r.stdout) : null, err: r.stderr };
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

test('sigmahuman factcheck: the same facts in other words pass', (t) => {
  const python = findPython();
  if (!python) return t.skip('python 3 not found');
  const r = factcheck(
    python,
    'Sales grew 40% to 4,500 units in March. "Ship it," said Ana. See `saveBest` at https://example.com/a.\n',
    'In March sales grew 40 percent, to four and a half thousand units. Ana said "Ship it," and you can read `saveBest` at https://example.com/a.\n',
  );
  assert.equal(r.status, 0, r.err + JSON.stringify(r.report));
  assert.equal(r.report.ok, true);
});

test('sigmahuman factcheck: a lost number, a new number and a changed code span fail', (t) => {
  const python = findPython();
  if (!python) return t.skip('python 3 not found');
  const r = factcheck(
    python,
    'The plant makes 1.2 million cars a year and `step` runs twice.\n',
    'The plant makes about 2 million cars a year and `tick` runs twice.\n',
  );
  assert.equal(r.status, 1);
  assert.ok(r.report.lost.includes('number 1.2e+06'), JSON.stringify(r.report.lost));
  assert.ok(r.report.added.includes('number 2e+06'), JSON.stringify(r.report.added));
  assert.ok(r.report.lost.some((line) => line.includes("'step'")));
});

test('sigmahuman factcheck: the sentence-length band is measured on both sides', (t) => {
  const python = findPython();
  if (!python) return t.skip('python 3 not found');
  const r = factcheck(
    python,
    'China builds a new power plant almost every week, and most of them burn coal for now.\n',
    'China builds plants. Almost every week. Most burn coal. For now.\n',
  );
  assert.equal(r.report.band_before.sentences, 1);
  assert.equal(r.report.band_after.sentences, 4);
  assert.ok(r.report.band_after.avg_words < r.report.band_before.avg_words);
});

test('sigmahuman ships the upstream MIT notice and the 26 upstream patterns', () => {
  const licence = readFileSync(join(root, 'sigmahuman', 'references', 'LICENSE-humanizer.txt'), 'utf8');
  assert.match(licence, /MIT License/);
  assert.match(licence, /Copyright \(c\) 2025 Siqi Chen/);
  const patterns = readFileSync(join(root, 'sigmahuman', 'references', 'patterns.md'), 'utf8');
  const numbered = [...patterns.matchAll(/^### (\d+)\. /gm)].map((m) => Number(m[1]));
  assert.deepEqual(numbered, Array.from({ length: 26 }, (_, i) => i + 1));
  const skill = readFileSync(join(root, 'sigmahuman', 'SKILL.md'), 'utf8');
  assert.match(skill, /blader\/humanizer/);
  assert.doesNotMatch(skill.split('## Credits')[0], /[–—]/, 'SKILL.md prose must follow its own dash rule');
  for (const lane of ['Ear', 'Book', 'Song', 'Chat', 'Docs', 'Post', 'Brief']) {
    assert.match(readFileSync(join(root, 'sigmahuman', 'references', 'lanes.md'), 'utf8'), new RegExp(`^## ${lane}`, 'm'));
  }
});

test('sigmahuman upstream: patterns A-F equal the vendored blader/humanizer copy', (t) => {
  const python = findPython();
  if (!python) return t.skip('python 3 not found');
  const r = spawnSync(python, ['-I', join(root, 'sigmahuman', 'scripts', 'upstream.py'), 'check'], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const meta = JSON.parse(readFileSync(join(root, 'sigmahuman', 'upstream', 'UPSTREAM.json'), 'utf8'));
  assert.match(meta.commit, /^[0-9a-f]{40}$/);
  const skill = readFileSync(join(root, 'sigmahuman', 'SKILL.md'), 'utf8');
  assert.ok(skill.includes(`blader/humanizer ${meta.version}`), 'SKILL.md names the vendored version');
});
