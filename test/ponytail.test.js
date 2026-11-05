import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { PONYTAIL_TAG, ponytailCheck, ponytailOff, ponytailOn } from '../src/ponytail.js';
import { runCli } from '../src/cli.js';

function tmpProject() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-pony-'));
}

const read = (root, rel) => fs.readFileSync(path.join(root, rel), 'utf8');

test('ponytail on: writes Claude, Codex and Pi project config', () => {
  const root = tmpProject();
  ponytailOn(root);
  const claude = JSON.parse(read(root, '.claude/settings.json'));
  assert.equal(claude.enabledPlugins['ponytail@ponytail'], true);
  assert.deepEqual(claude.extraKnownMarketplaces.ponytail.source, {
    source: 'github',
    repo: 'DietrichGebert/ponytail',
    ref: PONYTAIL_TAG,
  });
  assert.equal(claude.env.PONYTAIL_HIDE_STATUS, '1');
  assert.ok(claude.env.PONYTAIL_SUBAGENT_MATCHER);
  const codex = read(root, '.codex/config.toml');
  assert.match(codex, /\[plugins\."ponytail@ponytail"\]\nenabled = true/);
  assert.match(codex, new RegExp(`ref = "${PONYTAIL_TAG}"`));
  const pi = JSON.parse(read(root, '.pi/settings.json'));
  assert.deepEqual(pi.packages, [`git:github.com/DietrichGebert/ponytail@${PONYTAIL_TAG}`]);
  assert.match(read(root, '.gitignore'), /^\.pi\/git\/$/m);
  assert.deepEqual(ponytailCheck(root), { claude: 'on', codex: 'on', pi: 'on' });
});

test('ponytail on: keeps existing settings and runs twice without duplicates', () => {
  const root = tmpProject();
  fs.mkdirSync(path.join(root, '.claude'));
  fs.writeFileSync(path.join(root, '.claude/settings.json'), JSON.stringify({ env: { KEEP: 'x' }, model: 'opus' }));
  fs.mkdirSync(path.join(root, '.codex'));
  fs.writeFileSync(path.join(root, '.codex/config.toml'), 'model = "gpt"\n');
  fs.mkdirSync(path.join(root, '.pi'));
  fs.writeFileSync(path.join(root, '.pi/settings.json'), JSON.stringify({ packages: ['npm:other'] }));
  ponytailOn(root);
  ponytailOn(root);
  const claude = JSON.parse(read(root, '.claude/settings.json'));
  assert.equal(claude.model, 'opus');
  assert.equal(claude.env.KEEP, 'x');
  const codex = read(root, '.codex/config.toml');
  assert.ok(codex.startsWith('model = "gpt"\n'));
  assert.equal(codex.match(/ponytail@ponytail/g).length, 1);
  assert.equal(JSON.parse(read(root, '.pi/settings.json')).packages.length, 2);
  assert.equal(read(root, '.gitignore').match(/\.pi\/git\//g).length, 1);
});

test('ponytail off: removes only what on wrote', () => {
  const root = tmpProject();
  fs.mkdirSync(path.join(root, '.claude'));
  fs.writeFileSync(path.join(root, '.claude/settings.json'), JSON.stringify({ env: { KEEP: 'x' } }));
  ponytailOn(root);
  ponytailOff(root);
  assert.deepEqual(JSON.parse(read(root, '.claude/settings.json')), { env: { KEEP: 'x' } });
  assert.equal(fs.existsSync(path.join(root, '.codex/config.toml')), false);
  assert.equal(fs.existsSync(path.join(root, '.pi/settings.json')), false);
  assert.equal(fs.existsSync(path.join(root, '.gitignore')), false);
  assert.deepEqual(ponytailCheck(root), { claude: 'off', codex: 'off', pi: 'off' });
});

test('ponytail on: refuses a Codex file it would break', () => {
  for (const text of ['[marketplaces.ponytail]\nsource = "x"\n', '# sigmaskills ponytail begin\n[x]\n']) {
    const root = tmpProject();
    fs.mkdirSync(path.join(root, '.codex'));
    fs.writeFileSync(path.join(root, '.codex/config.toml'), text);
    assert.throws(() => ponytailOn(root), /config\.toml/);
    assert.equal(read(root, '.codex/config.toml'), text);
    assert.equal(fs.existsSync(path.join(root, '.claude/settings.json')), false);
  }
});

test('ponytail check: an empty project is off everywhere', () => {
  assert.deepEqual(ponytailCheck(tmpProject()), { claude: 'off', codex: 'off', pi: 'off' });
});

test('cli: ponytail --project, --check --json and --remove', async () => {
  const root = tmpProject();
  const out = [];
  const io = { stdout: { write: (s) => out.push(s) }, stderr: { write: (s) => out.push(s) } };
  assert.equal(await runCli(['ponytail', '--project', root], io), 0);
  out.length = 0;
  assert.equal(await runCli(['ponytail', '--check', '--json', '--project', root], io), 0);
  assert.deepEqual(JSON.parse(out.join('')).ponytail, { claude: 'on', codex: 'on', pi: 'on' });
  assert.equal(await runCli(['ponytail', '--remove', '--project', root], io), 0);
  out.length = 0;
  assert.equal(await runCli(['ponytail', '--check', '--project', root], io), 1);
  assert.match(out.join(''), /claude\s+off/);
});
