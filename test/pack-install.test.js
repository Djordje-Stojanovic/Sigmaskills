import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { describe, it as test } from 'node:test';
import { runCli } from '../src/cli.js';
import {
  ACME_PACK, commitAll, createMockIo, createRemote, createSandbox, writeSkills, writeUserConfig,
} from './pack-fixtures.js';

// Each test owns its sandbox and waits on child processes, so the file's tests run at once (the suite budget).
describe('pack-install', { concurrency: true }, () => {

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

});
