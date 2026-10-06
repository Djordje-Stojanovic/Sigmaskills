import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import { execFileSync, execSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { getCatalog, findPackageRoot } from '../src/catalog.js';
import { runCli } from '../src/cli.js';
import { extractRawCustomContent, injectRawCustomContent } from '../src/customization.js';
import {
  UNIVERSAL_PROJECT_DESTINATION,
  listProjectDestinationGroups,
  loadHostRegistry,
} from '../src/destinations.js';
import { pathExists } from '../src/links.js';
import { computeSkillRevisionAndHashes } from '../src/revision.js';
import { executeProjectInstall } from '../src/transaction.js';
import {
  UPDATE_SCHEMA_VERSION,
  createUpdatePlan,
  formatUpdateHuman,
  executeUpdate,
} from '../src/update.js';

const ROOT = findPackageRoot();

function createMockIo(env) {
  let stdout = '';
  let stderr = '';
  return {
    stdout: { write: (s) => { stdout += s; } },
    stderr: { write: (s) => { stderr += s; } },
    env,
    getStdout: () => stdout,
    getStderr: () => stderr,
  };
}

function hostGroups(projectRoot) {
  return listProjectDestinationGroups({
    registry: loadHostRegistry(ROOT),
    projectRoot,
    env: {},
  });
}

function installWrite(projectRoot, skillId, options = {}) {
  return executeProjectInstall({
    catalog: getCatalog(ROOT),
    skillId,
    projectRoot,
    packageRoot: ROOT,
    destinationGroups: hostGroups(projectRoot),
    selectedRoots: options.selectedRoots || [UNIVERSAL_PROJECT_DESTINATION],
    method: options.method,
  });
}

function snapshotTree(root) {
  const files = {};
  if (!pathExists(root)) return files;
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      const rel = path.relative(root, full).replace(/\\/g, '/');
      const stat = fs.lstatSync(full);
      if (stat.isDirectory() && !stat.isSymbolicLink()) walk(full);
      else if (stat.isSymbolicLink()) files[rel] = `link:${fs.readlinkSync(full)}`;
      else files[rel] = crypto.createHash('sha256').update(fs.readFileSync(full)).digest('hex');
    }
  };
  walk(root);
  return files;
}

function skillDir(root, skillId) {
  return path.join(root, '.agents', 'skills', skillId);
}

function refreshRecordedHashes(root, skillId, options = {}) {
  const dest = skillDir(root, skillId);
  const hashes = computeSkillRevisionAndHashes(dest);
  const statePath = path.join(root, '.agents', '.sigmaskills', 'state.json');
  const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
  const entry = state.skills[skillId];
  entry.baseHashes = hashes.files;
  entry.revision = hashes.revision;
  if (options.release) entry.release = options.release;
  if (Array.isArray(entry.copies)) {
    for (const copy of entry.copies) {
      if (copy.baseHashes) copy.baseHashes = hashes.files;
    }
  }
  fs.writeFileSync(statePath, `${JSON.stringify(state, null, 2)}\n`);
  const lockPath = path.join(root, 'skills-lock.json');
  if (fs.existsSync(lockPath)) {
    const lock = JSON.parse(fs.readFileSync(lockPath, 'utf8'));
    if (lock.skills?.[skillId]) lock.skills[skillId].revision = hashes.revision;
    if (options.release) lock.release = options.release;
    fs.writeFileSync(lockPath, `${JSON.stringify(lock, null, 2)}\n`);
  }
  return hashes;
}

function ageOfficial(root, skillId, release = '0.0.9') {
  const dest = skillDir(root, skillId);
  const skillMd = path.join(dest, 'SKILL.md');
  const original = fs.readFileSync(skillMd, 'utf8');
  fs.writeFileSync(
    skillMd,
    original.replace('## Personal instructions', '<!-- sigma-older -->\n\n## Personal instructions'),
    'utf8',
  );
  return refreshRecordedHashes(root, skillId, { release });
}

test('update: no-op when installed Release matches the running CLI', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-noop-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const before = snapshotTree(projectRoot);
    const plan = createUpdatePlan({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
    });
    assert.equal(plan.schemaVersion, UPDATE_SCHEMA_VERSION);
    assert.equal(plan.release.relation, 'same');
    assert.equal(plan.changed.length, 0);
    assert.equal(plan.unchanged[0].comparison, 'no-op');
    assert.equal(plan.changelog, '');
    assert.doesNotMatch(formatUpdateHuman(plan), /Blocked skills:|Malformed markers:|\(none\)/);

    const io = createMockIo();
    const code = await runCli(['update', '--yes', '--project', projectRoot], io);
    assert.equal(code, 0);
    assert.deepEqual(snapshotTree(projectRoot), before);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: upstream-only change restores official files and reports older Release', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-up-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    ageOfficial(projectRoot, 'sigmawrite');
    const plan = createUpdatePlan({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
    });
    assert.equal(plan.release.relation, 'older');
    assert.equal(plan.changed[0].comparison, 'upstream-only');
    assert.match(formatUpdateHuman(plan), /Running Release:.*\(newer\)/);
    assert.doesNotMatch(formatUpdateHuman(plan), /Prompt:/);
    assert.ok(plan.changed[0].diff.replaced.includes('SKILL.md'));

    const io = createMockIo();
    const code = await runCli(['update', '--yes', '--project', projectRoot], io);
    assert.equal(code, 0);
    const md = fs.readFileSync(path.join(skillDir(projectRoot, 'sigmawrite'), 'SKILL.md'), 'utf8');
    assert.equal(md.includes('<!-- sigma-older -->'), false);
    const state = JSON.parse(fs.readFileSync(path.join(projectRoot, '.agents', '.sigmaskills', 'state.json'), 'utf8'));
    assert.equal(state.skills.sigmawrite.revision, getCatalog(ROOT).skills.find((s) => s.id === 'sigmawrite').revision);
    assert.equal(state.skills.sigmawrite.release, getCatalog(ROOT).manifest.version);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: customization-only is unchanged; selected skip leaves the other skill aged', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-skip-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    installWrite(projectRoot, 'sigmabrief');
    const writeMd = path.join(skillDir(projectRoot, 'sigmawrite'), 'SKILL.md');
    const raw = '\r\nKeep CRLF  \n# heading\n<note>xml</note>\nno-final-newline';
    fs.writeFileSync(writeMd, injectRawCustomContent(fs.readFileSync(writeMd, 'utf8'), raw, 'sigmawrite'), 'utf8');
    ageOfficial(projectRoot, 'sigmabrief');

    const plan = createUpdatePlan({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
    });
    assert.equal(plan.unchanged.find((s) => s.id === 'sigmawrite').comparison, 'customization-only');
    assert.equal(plan.changed.find((s) => s.id === 'sigmabrief').comparison, 'upstream-only');

    const io = createMockIo();
    const code = await runCli(['update', '--skill', 'sigmawrite', '--project', projectRoot], io);
    assert.equal(code, 0);
    assert.equal(extractRawCustomContent(fs.readFileSync(writeMd, 'utf8'), 'sigmawrite'), raw);
    assert.equal(
      fs.readFileSync(path.join(skillDir(projectRoot, 'sigmabrief'), 'SKILL.md'), 'utf8').includes('<!-- sigma-older -->'),
      true,
    );
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: upstream plus populated custom preserves exact raw bytes', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-custom-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    ageOfficial(projectRoot, 'sigmawrite');
    const skillMd = path.join(skillDir(projectRoot, 'sigmawrite'), 'SKILL.md');
    const raw = '  unicode • café\n```md\ncode\n```\n';
    fs.writeFileSync(skillMd, injectRawCustomContent(fs.readFileSync(skillMd, 'utf8'), raw, 'sigmawrite'), 'utf8');

    const io = createMockIo();
    const code = await runCli(['update', '--yes', '--json', '--project', projectRoot], io);
    assert.equal(code, 0);
    const parsed = JSON.parse(io.getStdout());
    assert.equal(parsed.changed[0].comparison, 'upstream-and-customization');
    const after = fs.readFileSync(skillMd, 'utf8');
    assert.equal(extractRawCustomContent(after, 'sigmawrite'), raw);
    assert.equal(after.includes('<!-- sigma-older -->'), false);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

function setLocalDescription(root, skillId, entry = 'description: >-\n  Short local text. Do not use for code.\n') {
  const skillMd = path.join(skillDir(root, skillId), 'SKILL.md');
  fs.writeFileSync(skillMd, fs.readFileSync(skillMd, 'utf8').replace(/^description:.*\n/m, entry), 'utf8');
  return skillMd;
}

test('update: a local description alone is customization-only and a no-op (#94)', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-desc-noop-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    setLocalDescription(projectRoot, 'sigmawrite');
    const before = snapshotTree(projectRoot);
    const plan = createUpdatePlan({ catalog: getCatalog(ROOT), projectRoot, packageRoot: ROOT });
    assert.equal(plan.changed.length, 0);
    assert.equal(plan.unchanged[0].comparison, 'customization-only');

    const io = createMockIo();
    const code = await runCli(['update', '--yes', '--project', projectRoot], io);
    assert.equal(code, 0, io.getStderr());
    assert.deepEqual(snapshotTree(projectRoot), before);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: upstream change keeps the local description and ships the new files (#94)', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-desc-up-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    ageOfficial(projectRoot, 'sigmawrite');
    const entry = 'description: >-\r\n  Short local text. Do not use for code.\r\n';
    const skillMd = setLocalDescription(projectRoot, 'sigmawrite', entry);

    const plan = createUpdatePlan({ catalog: getCatalog(ROOT), projectRoot, packageRoot: ROOT });
    assert.equal(plan.changed[0].comparison, 'upstream-and-customization');
    assert.match(formatUpdateHuman(plan), /local description: kept/);

    const io = createMockIo();
    const code = await runCli(['update', '--yes', '--project', projectRoot], io);
    assert.equal(code, 0, io.getStderr());
    const after = fs.readFileSync(skillMd, 'utf8');
    assert.equal(after.includes('<!-- sigma-older -->'), false);
    assert.match(after, /^description: >-\n  Short local text\. Do not use for code\.\n/m);
    const official = fs.readFileSync(path.join(ROOT, 'sigmawrite', 'SKILL.md'), 'utf8');
    assert.equal(after.replace(/^description:[^]*?\n(?=\S)/m, ''), official.replace(/^description:.*\n/m, ''));
    const state = JSON.parse(fs.readFileSync(path.join(projectRoot, '.agents', '.sigmaskills', 'state.json'), 'utf8'));
    assert.deepEqual(state.skills.sigmawrite.baseHashes, getCatalog(ROOT).skills.find((s) => s.id === 'sigmawrite').files);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: an upstream description change with a local description still asks first (#94)', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-desc-both-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    setLocalDescription(projectRoot, 'sigmawrite', 'description: Older official text. Do not use for code.\n');
    refreshRecordedHashes(projectRoot, 'sigmawrite', { release: '0.0.9' });
    setLocalDescription(projectRoot, 'sigmawrite');
    const before = snapshotTree(projectRoot);

    const plan = createUpdatePlan({ catalog: getCatalog(ROOT), projectRoot, packageRoot: ROOT });
    assert.equal(plan.changed[0].comparison, 'concurrent');

    const io = createMockIo();
    const code = await runCli(['update', '--yes', '--project', projectRoot], io);
    assert.equal(code, 1);
    assert.match(io.getStderr(), /--outside-edit/);
    assert.deepEqual(snapshotTree(projectRoot), before);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: an untouched copy whose description changed upstream stays upstream-only (#94)', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-desc-untouched-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const skillMd = setLocalDescription(projectRoot, 'sigmawrite', 'description: Older official text. Do not use for code.\n');
    refreshRecordedHashes(projectRoot, 'sigmawrite', { release: '0.0.9' });

    const plan = createUpdatePlan({ catalog: getCatalog(ROOT), projectRoot, packageRoot: ROOT });
    assert.equal(plan.changed[0].comparison, 'upstream-only');
    assert.equal(plan.changed[0].localDescription, false);

    const io = createMockIo();
    assert.equal(await runCli(['update', '--yes', '--project', projectRoot], io), 0, io.getStderr());
    assert.equal(fs.readFileSync(skillMd, 'utf8'), fs.readFileSync(path.join(ROOT, 'sigmawrite', 'SKILL.md'), 'utf8'));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: links, managed copies, and Global Installation all keep the local description (#94)', async () => {
  const entry = 'description: >-\n  Short local text. Do not use for code.\n';
  const linked = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-desc-link-'));
  const copied = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-desc-copies-'));
  const homeDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-desc-global-'));
  try {
    installWrite(linked, 'sigmawrite', { selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'], method: 'link' });
    ageOfficial(linked, 'sigmawrite');
    setLocalDescription(linked, 'sigmawrite', entry);
    executeUpdate({ catalog: getCatalog(ROOT), projectRoot: linked, packageRoot: ROOT, skillIds: ['sigmawrite'] });
    const linkedHost = fs.readFileSync(path.join(linked, '.claude', 'skills', 'sigmawrite', 'SKILL.md'), 'utf8');
    assert.ok(linkedHost.includes(entry));
    assert.equal(linkedHost.includes('<!-- sigma-older -->'), false);

    installWrite(copied, 'sigmawrite', { selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'], method: 'copy' });
    ageOfficial(copied, 'sigmawrite');
    const host = path.join(copied, '.claude', 'skills', 'sigmawrite');
    fs.cpSync(skillDir(copied, 'sigmawrite'), host, { recursive: true, force: true });
    fs.copyFileSync(setLocalDescription(copied, 'sigmawrite', entry), path.join(host, 'SKILL.md'));
    executeUpdate({ catalog: getCatalog(ROOT), projectRoot: copied, packageRoot: ROOT, skillIds: ['sigmawrite'] });
    for (const dir of [skillDir(copied, 'sigmawrite'), host]) {
      const md = fs.readFileSync(path.join(dir, 'SKILL.md'), 'utf8');
      assert.ok(md.includes(entry));
      assert.equal(md.includes('<!-- sigma-older -->'), false);
    }

    const env = { ...process.env, HOME: homeDir, USERPROFILE: homeDir };
    executeProjectInstall({ catalog: getCatalog(ROOT), skillId: 'sigmawrite', scope: 'global', homeDir, packageRoot: ROOT, env });
    ageOfficial(homeDir, 'sigmawrite');
    const globalMd = setLocalDescription(homeDir, 'sigmawrite', entry);
    const io = createMockIo(env);
    assert.equal(await runCli(['update', '--global', '--yes'], io), 0, io.getStderr());
    const after = fs.readFileSync(globalMd, 'utf8');
    assert.ok(after.includes(entry));
    assert.equal(after.includes('<!-- sigma-older -->'), false);
  } finally {
    for (const dir of [linked, copied, homeDir]) fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('update: empty customization plus upstream still ships the empty block', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-empty-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const skillMd = path.join(skillDir(projectRoot, 'sigmawrite'), 'SKILL.md');
    const emptyRaw = extractRawCustomContent(fs.readFileSync(skillMd, 'utf8'), 'sigmawrite');
    ageOfficial(projectRoot, 'sigmawrite');
    executeUpdate({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
    });
    assert.equal(
      extractRawCustomContent(fs.readFileSync(skillMd, 'utf8'), 'sigmawrite'),
      emptyRaw,
    );
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: resource add, change, rename, and delete participate in the revision', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-files-'));
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-fixture-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const dest = skillDir(projectRoot, 'sigmawrite');
    fs.writeFileSync(path.join(dest, 'legacy.txt'), 'remove me', 'utf8');
    fs.writeFileSync(path.join(dest, 'renamed-from.md'), 'rename me', 'utf8');
    refreshRecordedHashes(projectRoot, 'sigmawrite', { release: '0.0.8' });

    fs.cpSync(path.join(ROOT, 'sigmawrite'), path.join(fixtureRoot, 'sigmawrite'), { recursive: true });
    fs.writeFileSync(path.join(fixtureRoot, 'sigmawrite', 'added.md'), 'new resource', 'utf8');
    fs.writeFileSync(path.join(fixtureRoot, 'sigmawrite', 'renamed-to.md'), 'rename me', 'utf8');
    const yaml = fs.readFileSync(path.join(fixtureRoot, 'sigmawrite', 'agents', 'openai.yaml'), 'utf8');
    fs.writeFileSync(path.join(fixtureRoot, 'sigmawrite', 'agents', 'openai.yaml'), `${yaml}\n# changed\n`, 'utf8');
    fs.writeFileSync(path.join(fixtureRoot, 'CHANGELOG.md'), '## [Unreleased]\n\n- fixture resources\n', 'utf8');
    const computed = computeSkillRevisionAndHashes(path.join(fixtureRoot, 'sigmawrite'));
    const catalog = getCatalog(ROOT);
    const fixtureCatalog = {
      ...catalog,
      manifest: { ...catalog.manifest, version: '0.1.1' },
      skills: catalog.skills.map((skill) => (
        skill.id === 'sigmawrite'
          ? { ...skill, revision: computed.revision, files: computed.files }
          : skill
      )),
    };

    const plan = createUpdatePlan({
      catalog: fixtureCatalog,
      projectRoot,
      packageRoot: fixtureRoot,
    });
    const skill = plan.changed.find((item) => item.id === 'sigmawrite');
    assert.ok(skill.diff.added.includes('added.md'));
    assert.ok(skill.diff.added.includes('renamed-to.md'));
    assert.ok(skill.diff.deleted.includes('legacy.txt'));
    assert.ok(skill.diff.deleted.includes('renamed-from.md'));
    assert.ok(skill.diff.replaced.includes('agents/openai.yaml'));

    executeUpdate({
      catalog: fixtureCatalog,
      projectRoot,
      packageRoot: fixtureRoot,
      skillIds: ['sigmawrite'],
    });
    assert.ok(fs.existsSync(path.join(dest, 'added.md')));
    assert.ok(fs.existsSync(path.join(dest, 'renamed-to.md')));
    assert.ok(!fs.existsSync(path.join(dest, 'legacy.txt')));
    assert.ok(!fs.existsSync(path.join(dest, 'renamed-from.md')));
    const state = JSON.parse(fs.readFileSync(path.join(projectRoot, '.agents', '.sigmaskills', 'state.json'), 'utf8'));
    assert.equal(state.skills.sigmawrite.revision, computed.revision);
    assert.deepEqual(state.skills.sigmawrite.baseHashes, computed.files);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
});

test('update: canonical owner updates links and matching copies together', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-owner-'));
  try {
    installWrite(projectRoot, 'sigmawrite', {
      selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
      method: 'link',
    });
    ageOfficial(projectRoot, 'sigmawrite');
    const canonicalMd = path.join(skillDir(projectRoot, 'sigmawrite'), 'SKILL.md');
    const raw = 'owner-custom\n';
    fs.writeFileSync(
      canonicalMd,
      injectRawCustomContent(fs.readFileSync(canonicalMd, 'utf8'), raw, 'sigmawrite'),
      'utf8',
    );

    executeUpdate({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
    });
    const host = path.join(projectRoot, '.claude', 'skills', 'sigmawrite');
    const hostStat = fs.lstatSync(host);
    assert.ok(hostStat.isSymbolicLink() || hostStat.isDirectory());
    if (hostStat.isSymbolicLink()) {
      assert.equal(
        path.resolve(path.dirname(host), fs.readlinkSync(host)),
        path.resolve(skillDir(projectRoot, 'sigmawrite')),
      );
    }
    const hostMd = fs.readFileSync(path.join(host, 'SKILL.md'), 'utf8');
    assert.equal(extractRawCustomContent(hostMd, 'sigmawrite'), raw);
    assert.equal(extractRawCustomContent(fs.readFileSync(canonicalMd, 'utf8'), 'sigmawrite'), raw);
    assert.equal(hostMd.includes('<!-- sigma-older -->'), false);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: independent managed copies receive the canonical customization together', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-copies-'));
  try {
    installWrite(projectRoot, 'sigmawrite', {
      selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
      method: 'copy',
    });
    ageOfficial(projectRoot, 'sigmawrite');
    const canonical = skillDir(projectRoot, 'sigmawrite');
    const host = path.join(projectRoot, '.claude', 'skills', 'sigmawrite');
    fs.cpSync(canonical, host, { recursive: true, force: true });
    const raw = 'copy-custom\n';
    const canonicalMd = path.join(canonical, 'SKILL.md');
    fs.writeFileSync(
      canonicalMd,
      injectRawCustomContent(fs.readFileSync(canonicalMd, 'utf8'), raw, 'sigmawrite'),
      'utf8',
    );
    fs.copyFileSync(canonicalMd, path.join(host, 'SKILL.md'));
    executeUpdate({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
    });
    assert.equal(fs.lstatSync(host).isSymbolicLink(), false);
    assert.equal(extractRawCustomContent(fs.readFileSync(canonicalMd, 'utf8'), 'sigmawrite'), raw);
    assert.equal(extractRawCustomContent(fs.readFileSync(path.join(host, 'SKILL.md'), 'utf8'), 'sigmawrite'), raw);
    assert.equal(fs.readFileSync(canonicalMd, 'utf8').includes('<!-- sigma-older -->'), false);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: a failure on a later skill still reports the skills already updated (#67)', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-partial-'));
  try {
    installWrite(projectRoot, 'sigmabrief');
    installWrite(projectRoot, 'sigmawrite');
    ageOfficial(projectRoot, 'sigmabrief');
    const writeMd = path.join(skillDir(projectRoot, 'sigmawrite'), 'SKILL.md');
    fs.writeFileSync(writeMd, fs.readFileSync(writeMd, 'utf8').replace('<sigmaskills-custom>', '<sigmaskills-custom>\n<sigmaskills-custom>'), 'utf8');

    assert.throws(
      () => executeUpdate({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        malformedMarkers: 'repair',
        skillIds: ['sigmabrief', 'sigmawrite'],
      }),
      (err) => /invalid repair/.test(err.message)
        && err.updatedSkills.length === 1
        && err.updatedSkills[0].id === 'sigmabrief'
        && err.updatedSkills[0].success === true,
    );

    ageOfficial(projectRoot, 'sigmabrief');
    const io = createMockIo();
    const code = await runCli(['update', '--yes', '--malformed-markers', 'repair', '--project', projectRoot], io);
    assert.equal(code, 1);
    assert.match(io.getStderr(), /invalid repair/);
    assert.match(io.getStderr(), /Updated before the failure: sigmabrief/);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: unknown schema, missing bundled revision, and unsafe drift do not mutate', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-stop-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const statePath = path.join(projectRoot, '.agents', '.sigmaskills', 'state.json');

    const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    state.schemaVersion = 99;
    fs.writeFileSync(statePath, `${JSON.stringify(state, null, 2)}\n`);
    const beforeSchema = snapshotTree(projectRoot);
    const schemaIo = createMockIo();
    const schemaCode = await runCli(['update', '--yes', '--project', projectRoot], schemaIo);
    assert.equal(schemaCode, 1);
    assert.match(schemaIo.getStderr(), /schemaVersion 99/);
    assert.deepEqual(snapshotTree(projectRoot), beforeSchema);

    state.schemaVersion = 1;
    fs.writeFileSync(statePath, `${JSON.stringify(state, null, 2)}\n`);
    const withGhost = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    withGhost.skills.ghostskill = {
      ...withGhost.skills.sigmawrite,
      destination: '.agents/skills/ghostskill',
    };
    const beforeGhost = snapshotTree(projectRoot);
    fs.writeFileSync(statePath, `${JSON.stringify(withGhost, null, 2)}\n`);
    const ghostIo = createMockIo();
    const ghostCode = await runCli(['update', '--yes', '--project', projectRoot], ghostIo);
    assert.equal(ghostCode, 1);
    assert.match(ghostIo.getStderr(), /missing bundled Skill Revision/);
    const afterGhost = snapshotTree(projectRoot);
    delete afterGhost['.agents/.sigmaskills/state.json'];
    const beforeGhostFiles = { ...beforeGhost };
    delete beforeGhostFiles['.agents/.sigmaskills/state.json'];
    assert.deepEqual(afterGhost, beforeGhostFiles);

    fs.writeFileSync(statePath, `${JSON.stringify(state, null, 2)}\n`);
    const skillMd = path.join(skillDir(projectRoot, 'sigmawrite'), 'SKILL.md');
    fs.writeFileSync(skillMd, fs.readFileSync(skillMd, 'utf8').replace('<sigmaskills-custom>', '<sigmaskills-custom>'), 'utf8');
    fs.writeFileSync(skillMd, `${fs.readFileSync(skillMd, 'utf8')}\n<sigmaskills-custom>\n`, 'utf8');
    const beforeDrift = snapshotTree(projectRoot);
    const driftIo = createMockIo();
    const driftCode = await runCli(['update', '--yes', '--project', projectRoot], driftIo);
    assert.equal(driftCode, 1);
    assert.match(driftIo.getStderr(), /unsafe drift|stopped update without mutation|malformed/);
    assert.deepEqual(snapshotTree(projectRoot), beforeDrift);
    const dry = createUpdatePlan({ catalog: getCatalog(ROOT), projectRoot, packageRoot: ROOT });
    assert.equal(dry.needsMarkerResolution[0].comparison, 'malformed-markers');
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: newer Release relation is reported and Global Installation uses the same transaction', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-newer-'));
  const homeDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-global-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const statePath = path.join(projectRoot, '.agents', '.sigmaskills', 'state.json');
    const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    state.skills.sigmawrite.release = '9.9.9';
    fs.writeFileSync(statePath, `${JSON.stringify(state, null, 2)}\n`);
    const plan = createUpdatePlan({ catalog: getCatalog(ROOT), projectRoot, packageRoot: ROOT });
    assert.equal(plan.release.relation, 'newer');

    executeProjectInstall({
      catalog: getCatalog(ROOT),
      skillId: 'sigmawrite',
      scope: 'global',
      homeDir,
      packageRoot: ROOT,
      env: { ...process.env, HOME: homeDir, USERPROFILE: homeDir },
    });
    ageOfficial(homeDir, 'sigmawrite');
    const beforeLock = fs.existsSync(path.join(homeDir, 'skills-lock.json'));
    const io = createMockIo({ ...process.env, HOME: homeDir, USERPROFILE: homeDir });
    const code = await runCli(['update', '--global', '--yes', '--project', homeDir], io);
    assert.equal(code, 0);
    assert.equal(beforeLock, false);
    assert.ok(!fs.existsSync(path.join(homeDir, 'skills-lock.json')));
    assert.equal(
      fs.readFileSync(path.join(skillDir(homeDir, 'sigmawrite'), 'SKILL.md'), 'utf8').includes('<!-- sigma-older -->'),
      false,
    );
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});

test('cli: update --dry-run groups skills and writes nothing; missing flags fail closed', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-dry-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    ageOfficial(projectRoot, 'sigmawrite');
    const before = snapshotTree(projectRoot);
    const io = createMockIo();
    const code = await runCli(['update', '--dry-run', '--project', projectRoot], io);
    assert.equal(code, 0);
    assert.match(io.getStdout(), /Changed skills:/);
    assert.doesNotMatch(io.getStdout(), /Unchanged skills:/);
    assert.match(io.getStdout(), /Changelog:/);
    const jsonIo = createMockIo();
    assert.equal(await runCli(['update', '--dry-run', '--json', '--project', projectRoot], jsonIo), 0);
    const payload = JSON.parse(jsonIo.getStdout());
    assert.deepEqual(Object.keys(payload), ['schemaVersion', 'command', 'scope', 'dryRun', 'release', 'changelog',
      'owner', 'prompt', 'changed', 'unchanged', 'blocked', 'needsResolution', 'needsMarkerResolution', 'retired', 'skills',
      'selected', 'skipped', 'outsideEdit', 'malformedMarkers', 'results']);
    assert.deepEqual(Object.keys(payload.release), ['installed', 'running', 'relation']);
    assert.equal(payload.release.relation, 'older');
    assert.deepEqual(snapshotTree(projectRoot), before);

    const failIo = createMockIo();
    const failCode = await runCli(['update', '--project', projectRoot], failIo);
    assert.equal(failCode, 1);
    assert.match(failIo.getStderr(), /--yes|--skill/);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('packed CLI updates Project and Global Installation while preserving customization', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-pack-update-'));
  try {
    const packOutput = execSync(`npm pack --pack-destination "${tmpDir}"`, {
      cwd: ROOT,
      encoding: 'utf8',
    }).trim();
    const tarballFileName = packOutput.split(/\r?\n/).pop()?.trim();
    const tarballPath = path.join(tmpDir, tarballFileName);
    const appDir = path.join(tmpDir, 'test-app');
    fs.mkdirSync(appDir, { recursive: true });
    execSync('npm init -y', { cwd: appDir, encoding: 'utf8', stdio: 'pipe' });
    execSync(`npm install "${tarballPath}"`, { cwd: appDir, encoding: 'utf8', stdio: 'pipe' });
    const installedBin = path.join(appDir, 'node_modules', '@djordje-stojanovic', 'sigmaskills', 'bin', 'sigmaskills.js');

    const project = path.join(tmpDir, 'proj');
    execFileSync('node', [installedBin, 'install', 'sigmawrite', '--project', project], {
      cwd: appDir,
      encoding: 'utf8',
    });
    const dest = path.join(project, '.agents', 'skills', 'sigmawrite');
    const skillMd = path.join(dest, 'SKILL.md');
    const older = fs.readFileSync(skillMd, 'utf8').replace(
      '## Personal instructions',
      '<!-- sigma-older -->\n\n## Personal instructions',
    );
    fs.writeFileSync(skillMd, older, 'utf8');
    const hashes = computeSkillRevisionAndHashes(dest);
    const statePath = path.join(project, '.agents', '.sigmaskills', 'state.json');
    const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    state.skills.sigmawrite.baseHashes = hashes.files;
    state.skills.sigmawrite.revision = hashes.revision;
    state.skills.sigmawrite.release = '0.0.9';
    fs.writeFileSync(statePath, `${JSON.stringify(state, null, 2)}\n`);
    const raw = 'packed-custom <tag>\n';
    fs.writeFileSync(skillMd, injectRawCustomContent(fs.readFileSync(skillMd, 'utf8'), raw, 'sigmawrite'), 'utf8');

    const updated = execFileSync(
      'node',
      [installedBin, 'update', '--yes', '--json', '--project', project],
      { cwd: appDir, encoding: 'utf8' },
    );
    const parsed = JSON.parse(updated);
    assert.equal(parsed.command, 'update');
    assert.ok(parsed.selected.includes('sigmawrite'));
    const after = fs.readFileSync(skillMd, 'utf8');
    assert.equal(extractRawCustomContent(after, 'sigmawrite'), raw);
    assert.equal(after.includes('<!-- sigma-older -->'), false);

    const homeDir = path.join(tmpDir, 'home');
    fs.mkdirSync(homeDir, { recursive: true });
    execFileSync(
      'node',
      [installedBin, 'install', 'sigmabrief', '--global', '--yes'],
      {
        cwd: appDir,
        encoding: 'utf8',
        env: { ...process.env, HOME: homeDir, USERPROFILE: homeDir },
      },
    );
    const globalDest = path.join(homeDir, '.agents', 'skills', 'sigmabrief');
    const globalMd = path.join(globalDest, 'SKILL.md');
    fs.writeFileSync(
      globalMd,
      fs.readFileSync(globalMd, 'utf8').replace(
        '## Personal instructions',
        '<!-- sigma-older -->\n\n## Personal instructions',
      ),
      'utf8',
    );
    const globalHashes = computeSkillRevisionAndHashes(globalDest);
    const globalStatePath = path.join(homeDir, '.agents', '.sigmaskills', 'state.json');
    const globalState = JSON.parse(fs.readFileSync(globalStatePath, 'utf8'));
    globalState.skills.sigmabrief.baseHashes = globalHashes.files;
    globalState.skills.sigmabrief.revision = globalHashes.revision;
    fs.writeFileSync(globalStatePath, `${JSON.stringify(globalState, null, 2)}\n`);
    execFileSync(
      'node',
      [installedBin, 'update', '--global', '--yes'],
      {
        cwd: appDir,
        encoding: 'utf8',
        env: { ...process.env, HOME: homeDir, USERPROFILE: homeDir },
      },
    );
    assert.equal(
      fs.readFileSync(globalMd, 'utf8').includes('<!-- sigma-older -->'),
      false,
    );
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('update: a retired skill is reported and left untouched instead of blocking the update', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-retired-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const statePath = path.join(projectRoot, '.agents', '.sigmaskills', 'state.json');
    const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    const retiredDir = path.join(projectRoot, '.agents', 'skills', 'sigmaperformance');
    fs.cpSync(path.join(projectRoot, '.agents', 'skills', 'sigmawrite'), retiredDir, { recursive: true });
    state.skills.sigmaperformance = { ...state.skills.sigmawrite, destination: '.agents/skills/sigmaperformance' };
    fs.writeFileSync(statePath, `${JSON.stringify(state, null, 2)}\n`);
    const before = snapshotTree(retiredDir);

    const io = createMockIo();
    const code = await runCli(['update', '--yes', '--project', projectRoot], io);
    assert.equal(code, 0, io.getStderr());
    assert.match(io.getStdout(), /Retired skills[\s\S]*sigmaperformance/);
    assert.match(io.getStdout(), /uninstall --skill sigmaperformance/);
    assert.deepEqual(snapshotTree(retiredDir), before);

    const jsonIo = createMockIo();
    assert.equal(await runCli(['update', '--dry-run', '--json', '--project', projectRoot], jsonIo), 0);
    assert.deepEqual(JSON.parse(jsonIo.getStdout()).retired, ['sigmaperformance']);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update preview: release relation is shown from the running version perspective', () => {
  for (const [relation, label] of [['older', 'newer'], ['same', 'same'], ['newer', 'older']]) {
    const plan = { release: { installed: '1.0.0', running: '2.0.0', relation }, skills: [] };
    assert.match(formatUpdateHuman(plan), new RegExp(`Running Release:.*\\(${label}\\)`));
    assert.equal(plan.release.relation, relation);
  }
});

test('update preview: includes each release newer than installed through running only', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-notes-'));
  const packageRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-update-log-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    refreshRecordedHashes(projectRoot, 'sigmawrite', { release: '0.1.0' });
    const catalog = getCatalog(ROOT);
    catalog.manifest.version = '0.3.0';
    fs.writeFileSync(path.join(packageRoot, 'CHANGELOG.md'), '# Changelog\n\n## [Unreleased]\n\n- future\n\n## [0.4.0]\n- fourth\n\n## [0.3.0]\n- third\n\n## [0.2.0]\n- second\n\n## [0.1.0]\n- first\n');
    const plan = createUpdatePlan({ catalog, projectRoot, packageRoot });
    assert.match(plan.changelog, /third/);
    assert.match(plan.changelog, /second/);
    assert.doesNotMatch(plan.changelog, /future|fourth|first/);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
    fs.rmSync(packageRoot, { recursive: true, force: true });
  }
});
