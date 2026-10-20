import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { runCli } from '../src/cli.js';
import {
  ACME_PACK, commitAll, createMockIo, createRemote, createSandbox, writeSkills, writeUserConfig,
} from './pack-fixtures.js';

function setup() {
  const box = createSandbox();
  const remote = createRemote(box.remotes, 'acme/skills', { alpha: 'Alpha skill.', beta: 'Beta skill.' });
  writeUserConfig(box.home, { packs: [ACME_PACK] });
  const run = async (args) => {
    const io = createMockIo(box.env);
    const code = await runCli([...args, '--project', box.project, '--no-color'], io);
    return { code, out: io.getStdout(), err: io.getStderr() };
  };
  return { box, remote, run };
}

const alpha = (box, ...rest) => path.join(box.project, '.agents', 'skills', 'alpha', ...rest);

test('pack install: a preset copies each skill once and links the host folder to it', async () => {
  const { box, run } = setup();
  try {
    const { code, out, err } = await run(['install', '--preset', 'acme', '--agent', 'claude']);
    assert.equal(code, 0, err);
    assert.match(out, /2 skills installed/);
    assert.match(out, /Acme\s+2 of 2/);
    assert.match(out, /\.claude\/skills\s+linked\s+Claude Code/);
    assert.ok(fs.existsSync(alpha(box, 'SKILL.md')));
    assert.ok(fs.existsSync(alpha(box, 'references', 'note.md')), 'the whole folder is copied');
    const link = path.join(box.project, '.claude', 'skills', 'alpha');
    assert.ok(fs.lstatSync(link).isSymbolicLink());
    assert.equal(fs.realpathSync(link), fs.realpathSync(alpha(box)));
    const state = JSON.parse(fs.readFileSync(path.join(box.project, '.agents', '.sigmaskills', 'packs.json'), 'utf8'));
    assert.deepEqual(Object.keys(state.skills).sort(), ['alpha', 'beta']);
    assert.equal(state.skills.alpha.pack, 'acme');
    assert.deepEqual(state.skills.alpha.roots, ['.claude/skills']);
    assert.ok(!fs.existsSync(path.join(box.project, '.git')), 'no clone is left in the project');
  } finally {
    box.cleanup();
  }
});

test('pack install: --copy writes a full copy into the host folder', async () => {
  const { box, run } = setup();
  try {
    const { code, err } = await run(['install', 'alpha', '--agent', 'claude', '--copy']);
    assert.equal(code, 0, err);
    const copy = path.join(box.project, '.claude', 'skills', 'alpha');
    assert.ok(!fs.lstatSync(copy).isSymbolicLink());
    assert.ok(fs.existsSync(path.join(copy, 'references', 'note.md')));
  } finally {
    box.cleanup();
  }
});

test('pack install: running it again changes nothing', async () => {
  const { box, run } = setup();
  try {
    await run(['install', '--preset', 'acme', '--agent', 'claude']);
    const again = await run(['install', '--preset', 'acme', '--agent', 'claude']);
    assert.equal(again.code, 0);
    assert.match(again.out, /already up to date/);
  } finally {
    box.cleanup();
  }
});

test('pack install: --dry-run fetches and reports but writes nothing', async () => {
  const { box, run } = setup();
  try {
    const { code, out } = await run(['install', '--preset', 'acme', '--dry-run']);
    assert.equal(code, 0);
    assert.match(out, /Dry run: would install 2 skills/);
    assert.ok(!fs.existsSync(path.join(box.project, '.agents')));
  } finally {
    box.cleanup();
  }
});

test('pack install: --json prints one entry per skill', async () => {
  const { box, run } = setup();
  try {
    const { code, out } = await run(['install', '--preset', 'acme', '--json']);
    assert.equal(code, 0);
    const parsed = JSON.parse(out);
    assert.equal(parsed.schemaVersion, 1);
    assert.deepEqual(parsed.entries.map((entry) => [entry.id, entry.status]), [['alpha', 'installed'], ['beta', 'installed']]);
  } finally {
    box.cleanup();
  }
});

test('pack install: Sigma skills and pack skills install together', async () => {
  const { box, run } = setup();
  try {
    const { code, out, err } = await run(['install', '--preset', 'acme', 'sigmawrite', '--agent', 'claude']);
    assert.equal(code, 0, err);
    assert.match(out, /3 skills installed/);
    assert.ok(fs.existsSync(path.join(box.project, '.agents', 'skills', 'sigmawrite', 'SKILL.md')));
    assert.ok(fs.existsSync(alpha(box, 'SKILL.md')));
    const status = await run(['status']);
    assert.match(status.out, /SigmaWrite/);
    assert.match(status.out, /Pack skills \(2\)/);
    assert.match(status.out, /alpha\s+\[acme\]\s+clean/);
  } finally {
    box.cleanup();
  }
});

test('pack install: a folder Sigma does not manage stays, unless --force backs it up', async () => {
  const { box, run } = setup();
  try {
    fs.mkdirSync(alpha(box), { recursive: true });
    fs.writeFileSync(alpha(box, 'SKILL.md'), 'my own alpha');
    const kept = await run(['install', 'alpha']);
    assert.equal(kept.code, 0);
    assert.match(kept.out, /1 kept \(folder in the way\)/);
    assert.equal(fs.readFileSync(alpha(box, 'SKILL.md'), 'utf8'), 'my own alpha');

    const forced = await run(['install', 'alpha', '--force']);
    assert.equal(forced.code, 0, forced.err);
    assert.match(forced.out, /backup/);
    assert.match(fs.readFileSync(alpha(box, 'SKILL.md'), 'utf8'), /Alpha skill/);
    const backups = fs.readdirSync(path.join(box.project, '.agents', '.sigmaskills', 'pack-backups'));
    assert.equal(backups.length, 1);
    assert.equal(fs.readFileSync(path.join(box.project, '.agents', '.sigmaskills', 'pack-backups', backups[0], 'SKILL.md'), 'utf8'), 'my own alpha');
  } finally {
    box.cleanup();
  }
});

test('pack update: new upstream content replaces clean copies and local edits stay', async () => {
  const { box, remote, run } = setup();
  try {
    await run(['install', '--preset', 'acme', '--agent', 'claude']);
    writeSkills(remote, { alpha: 'Alpha skill, version 2.', beta: 'Beta skill, version 2.' });
    commitAll(remote);
    fs.appendFileSync(path.join(box.project, '.agents', 'skills', 'beta', 'SKILL.md'), '\nmy edit\n');

    const preview = await run(['update', '--dry-run']);
    assert.equal(preview.code, 0, preview.err);
    assert.match(preview.out, /Dry run/);
    assert.doesNotMatch(fs.readFileSync(alpha(box, 'SKILL.md'), 'utf8'), /version 2/);

    const applied = await run(['update', '--yes']);
    assert.equal(applied.code, 0, applied.err);
    assert.match(applied.out, /1 updated/);
    assert.match(applied.out, /1 kept \(local edits\)/);
    assert.match(fs.readFileSync(alpha(box, 'SKILL.md'), 'utf8'), /version 2/);
    assert.match(fs.readFileSync(path.join(box.project, '.agents', 'skills', 'beta', 'SKILL.md'), 'utf8'), /my edit/);
    assert.ok(fs.lstatSync(path.join(box.project, '.claude', 'skills', 'alpha')).isSymbolicLink(), 'the host link survives an update');
  } finally {
    box.cleanup();
  }
});

test('pack update: --skill updates only the named pack skill', async () => {
  const { box, remote, run } = setup();
  try {
    await run(['install', '--preset', 'acme']);
    writeSkills(remote, { alpha: 'Alpha skill, version 2.', beta: 'Beta skill, version 2.' });
    commitAll(remote);
    const { code, err } = await run(['update', '--skill', 'beta']);
    assert.equal(code, 0, err);
    assert.match(fs.readFileSync(path.join(box.project, '.agents', 'skills', 'beta', 'SKILL.md'), 'utf8'), /version 2/);
    assert.doesNotMatch(fs.readFileSync(alpha(box, 'SKILL.md'), 'utf8'), /version 2/);
  } finally {
    box.cleanup();
  }
});

test('pack uninstall: removes the copy, the links, and the record', async () => {
  const { box, run } = setup();
  try {
    await run(['install', '--preset', 'acme', '--agent', 'claude']);
    const refused = await run(['uninstall', '--skill', 'alpha']);
    assert.equal(refused.code, 1);
    assert.match(refused.err, /requires --yes/);

    const { code, out, err } = await run(['uninstall', '--skill', 'alpha', '--yes']);
    assert.equal(code, 0, err);
    assert.match(out, /1 skill removed/);
    assert.ok(!fs.existsSync(alpha(box)));
    assert.ok(!fs.existsSync(path.join(box.project, '.claude', 'skills', 'alpha')));
    assert.ok(fs.existsSync(path.join(box.project, '.agents', 'skills', 'beta', 'SKILL.md')), 'other skills stay');
    const state = JSON.parse(fs.readFileSync(path.join(box.project, '.agents', '.sigmaskills', 'packs.json'), 'utf8'));
    assert.deepEqual(Object.keys(state.skills), ['beta']);

    const all = await run(['uninstall', '--all', '--yes']);
    assert.equal(all.code, 0, all.err);
    assert.ok(!fs.existsSync(path.join(box.project, '.agents', 'skills', 'beta')));
  } finally {
    box.cleanup();
  }
});

test('pack uninstall: a copy with local edits stays until --force', async () => {
  const { box, run } = setup();
  try {
    await run(['install', 'alpha']);
    fs.appendFileSync(alpha(box, 'SKILL.md'), '\nmine\n');
    const kept = await run(['uninstall', '--skill', 'alpha', '--yes']);
    assert.match(kept.out, /1 kept \(local edits\)/);
    assert.ok(fs.existsSync(alpha(box, 'SKILL.md')));
    const forced = await run(['uninstall', '--skill', 'alpha', '--yes', '--force']);
    assert.equal(forced.code, 0, forced.err);
    assert.ok(!fs.existsSync(alpha(box)));
    assert.equal(fs.readdirSync(path.join(box.project, '.agents', '.sigmaskills', 'pack-backups')).length, 1);
  } finally {
    box.cleanup();
  }
});

test('pack install: a failing source marks its skills failed and exits 1', async () => {
  const { box, run } = setup();
  try {
    writeUserConfig(box.home, {
      packs: [{ ...ACME_PACK, sources: [{ ...ACME_PACK.sources[0], repo: 'acme/missing' }] }],
    });
    const { code, out } = await run(['install', '--preset', 'acme']);
    assert.equal(code, 1);
    assert.match(out, /2 failed/);
    assert.match(out, /could not fetch acme\/missing/);
  } finally {
    box.cleanup();
  }
});

test('pack install: a folder source installs from a local folder', async () => {
  const { box, run } = setup();
  try {
    const folder = path.join(box.root, 'local-skills');
    writeSkills(folder, { 'local-one': 'One.', 'local-two': 'Two.' }, '.');
    writeUserConfig(box.home, { packs: [{ id: 'local', title: 'Local', sources: [{ type: 'dir', path: folder }] }] });
    const { code, err } = await run(['install', '--preset', 'local']);
    assert.equal(code, 0, err);
    assert.ok(fs.existsSync(path.join(box.project, '.agents', 'skills', 'local-two', 'SKILL.md')));
  } finally {
    box.cleanup();
  }
});

test('pack install: global scope needs --yes and writes under the home folder', async () => {
  const { box, run } = setup();
  try {
    const refused = await run(['install', '--preset', 'acme', '--global']);
    assert.equal(refused.code, 1);
    assert.match(refused.err, /requires both --global and --yes/);

    const { code, err } = await run(['install', '--preset', 'acme', '--global', '--yes', '--agent', 'claude']);
    assert.equal(code, 0, err);
    assert.ok(fs.existsSync(path.join(box.home, '.agents', 'skills', 'alpha', 'SKILL.md')));
    assert.ok(fs.lstatSync(path.join(box.home, '.claude', 'skills', 'alpha')).isSymbolicLink());
    assert.ok(!fs.existsSync(path.join(box.project, '.agents')));
    const status = await run(['status', '--global']);
    assert.match(status.out, /Pack skills \(2\)/);
  } finally {
    box.cleanup();
  }
});
