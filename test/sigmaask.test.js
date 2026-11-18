import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { buildCatalog, renderCatalog, CATALOG_PATH } from '../scripts/sigmaask-catalog.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SCRIPT = path.join(ROOT, 'sigmaask', 'scripts', 'ask.mjs');

test('sigmaask: catalog.json matches the registry (run node scripts/sigmaask-catalog.js)', () => {
  const onDisk = fs.readFileSync(CATALOG_PATH, 'utf8').replace(/\r\n/g, '\n');
  assert.equal(onDisk, renderCatalog(buildCatalog()));
});

test('sigmaask: every retired skill names its replacement', () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, 'manifest.json'), 'utf8'));
  for (const id of manifest.retired) assert.ok(manifest.replacedBy[id], `manifest.json replacedBy lacks ${id}`);
});

test('sigmaask: SKILL.md stays small (about 1,500 o200k tokens)', () => {
  // shortcut: bytes / 3.5 stands in for tiktoken, which Node does not ship.
  const bytes = fs.statSync(path.join(ROOT, 'sigmaask', 'SKILL.md')).size;
  assert.ok(bytes / 3.5 <= 1500, `sigmaask/SKILL.md is about ${Math.round(bytes / 3.5)} tokens`);
});

function skill(dir, id) {
  fs.mkdirSync(path.join(dir, id), { recursive: true });
  fs.writeFileSync(path.join(dir, id, 'SKILL.md'), `---\nname: ${id}\ndescription: x\n---\n`);
}

function run(home, project, ...args) {
  const env = { ...process.env, HOME: home, USERPROFILE: home, APPDATA: path.join(home, 'appdata') };
  for (const key of ['XDG_CONFIG_HOME', 'CLAUDE_CONFIG_DIR', 'CODEX_HOME', 'HERMES_HOME', 'VIBE_HOME', 'AUTOHAND_HOME']) delete env[key];
  const result = spawnSync(process.execPath, [SCRIPT, '--offline', '--project', project, ...args], { env, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  return result.stdout;
}

test('sigmaask: the scan finds hosts, installs, retired skills, duplicates and stale packs', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'sigmaask-home-'));
  const project = path.join(home, 'repo');
  try {
    skill(path.join(home, '.claude', 'skills'), 'sigmareview');
    skill(path.join(home, '.agents', 'skills'), 'sigmareview'); // a second, separate copy
    skill(path.join(home, '.agents', 'skills'), 'grill-me');
    skill(path.join(home, '.cursor', 'skills'), 'sigmarefactor'); // retired
    skill(path.join(home, '.cursor', 'skills'), 'my-own-skill');
    skill(path.join(project, '.agents', 'skills'), 'grill-me'); // project copy shadows the global one
    fs.mkdirSync(path.join(home, '.codex'));
    fs.mkdirSync(path.join(home, '.agents', '.sigmaskills'), { recursive: true });
    fs.writeFileSync(path.join(home, '.agents', '.sigmaskills', 'packs.json'), JSON.stringify({
      skills: { 'grill-me': { pack: 'mattpocock', source: 'mattpocock/skills', revision: '0'.repeat(40) } },
    }));

    const out = run(home, project);
    assert.match(out, /^hosts: .*Claude Code/m);
    assert.match(out, /^hosts: .*Codex/m);
    assert.match(out, /^hosts: .*Cursor/m);
    assert.match(out, /^sigma: 1\/\d+ installed · missing /m);
    assert.match(out, /^packs: mattpocock 1\/\d+ \(1 out of date\) · update: /m);
    assert.match(out, /^retired: sigmarefactor → use sigmamusk/m);
    assert.match(out, /^duplicate: sigmareview ×2 /m);
    assert.match(out, /^project copies shadow global ones: 1 \(grill-me\)/m);
    assert.match(out, /^other skills \(in no pack\): 1: my-own-skill/m);

    const ask = run(home, project, 'pptx', 'slides');
    assert.match(ask, /^ {2}pptx \[anthropic\] .*\| not installed$/m);
    assert.match(ask, /install: npx @djordje-stojanovic\/sigmaskills install <id> --global --yes/);

    assert.match(run(home, project, '--where', 'sigmareview'), /^installed: .*sigmareview[\\/]SKILL\.md/m);
    assert.match(run(home, project, '--where', 'pptx'), /raw\.githubusercontent\.com\/anthropics\/skills\/[0-9a-f]{40}\/skills\/pptx\/SKILL\.md/);
    assert.match(run(home, project, '--where', 'sigmarefactor'), /retired: use sigmamusk/);
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});
