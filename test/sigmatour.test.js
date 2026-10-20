import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const helper = join(root, 'sigmatour', 'scripts', 'sigmatour.py');

function findPython() {
  for (const cmd of ['python3', 'python', 'py']) {
    const r = spawnSync(cmd, ['--version'], { encoding: 'utf8' });
    if (r.status === 0 && /Python 3\.(\d+)/.test(r.stdout + r.stderr)) return cmd;
  }
  return null;
}

function py(t, ...args) {
  const python = findPython();
  if (!python) {
    t.skip('python 3 not found');
    return null;
  }
  return spawnSync(python, [helper, ...args], { cwd: root, encoding: 'utf8', env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
}

// sigmatour.py measures a repo in a temp folder: no network, no real repo written.
test('sigmatour helper selftest passes (scan, build, check)', (t) => {
  const r = py(t, 'selftest');
  if (!r) return;
  assert.equal(r.status, 0, (r.stdout || '') + (r.stderr || ''));
  assert.match(r.stdout, /selftest ok/);
});

test('scan holds the README against the repo and never writes into it', (t) => {
  const dir = mkdtempSync(join(tmpdir(), 'sigmatour-'));
  try {
    const repo = join(dir, 'shop');
    mkdirSync(join(repo, 'server'), { recursive: true });
    writeFileSync(join(repo, 'package.json'), JSON.stringify({ name: 'shop', scripts: { start: 'node server/index.js', seed: 'node seed.js' } }));
    writeFileSync(join(repo, 'server', 'index.js'), 'const port = process.env.SHOP_PORT || 3000;\n// FIXME: no auth yet\nmodule.exports = port;\n');
    writeFileSync(join(repo, 'README.md'), '# Shop\n\n```sh\n$ npm start\n$ npm run migrate\n```\n\nThe API lives in `server/index.js`.\n');
    const r = py(t, 'scan', repo, '--json');
    if (!r) return;
    assert.equal(r.status, 0, r.stderr);
    const d = JSON.parse(r.stdout);
    assert.deepEqual(d.readme.commands.map((c) => [c.cmd, c.ok]), [['npm start', true], ['npm run migrate', false]]);
    assert.deepEqual(d.readme.env_hidden.map((e) => e.name), ['SHOP_PORT']);
    assert.deepEqual(d.readme.scripts_unmentioned, ['seed']);
    assert.deepEqual(d.readme.notes, { FIXME: 1 });
    assert.ok(d.entries.mains.includes('server/index.js'));
    assert.equal(d.minutes, 15);
    assert.equal(readFileSync(join(repo, 'README.md'), 'utf8').includes('npm run migrate'), true);
    const page = join(dir, 'shop-tour.html');
    assert.equal(py(t, 'build', repo, '--out', page, '--minutes', '30').status, 0);
    const html = readFileSync(page, 'utf8');
    assert.match(html, /id="sigmatour-data">\{"name":"shop"/);
    const check = py(t, 'check', page);
    assert.equal(check.status, 1, 'FILL markers block');
    assert.match(check.stdout, /FILL left/);
    assert.match(check.stdout, /the target is 30 min/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('the tour template carries FILL markers, every stop and every drawn figure', () => {
  const html = readFileSync(join(root, 'sigmatour', 'assets', 'tour-template.html'), 'utf8');
  assert.match(html, /\bFILL\b/);
  for (const stop of ['What it does', 'The repo in numbers', 'How it works', 'One request, end to end', 'Examples, run end to end', 'What the README says', 'Where things are', 'Try it yourself', 'Your questions']) {
    assert.ok(html.includes(stop), `template is missing the stop "${stop}"`);
  }
  for (const id of ['sigmatour-data', 'map-notes', 'folder-notes', 'explorer', 'numbers', 'history', 'claims', 'entries', 'trace']) {
    assert.ok(html.includes(`id="${id}"`), `template is missing #${id}`);
  }
  assert.ok((html.match(/class="step"/g) || []).length >= 4, 'the trace starts with 4 steps');
  assert.match(html, /--canvas: #09090b/, 'the template wears the Black-Green tokens of DESIGN.md');
});
