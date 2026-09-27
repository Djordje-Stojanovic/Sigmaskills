import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { loadSkillBaselines } from '../src/adoption.js';
import { hashSkillsAtRef, readSkillTreeAtRef } from '../scripts/baselines.js';
import { getCatalog, findPackageRoot } from '../src/catalog.js';
import { createInstallPlan } from '../src/plan.js';
import { formatReleaseHuman, writeReleaseIdentities } from '../scripts/release.js';
import { computeSkillRevision } from '../src/revision.js';
import { executeProjectInstall } from '../src/transaction.js';

const ROOT = findPackageRoot();
const EARLIER_RELEASES = ['0.1.0', '0.2.0', '0.2.1', '0.3.0'];

function plantTree(dest, tree) {
  for (const [rel, bytes] of Object.entries(tree)) {
    const file = path.join(dest, ...rel.split('/'));
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, bytes);
  }
}

test('baselines: the bundled file holds every earlier Release, rebuilt exactly from its git tag', () => {
  const baselines = loadSkillBaselines(ROOT);
  for (const release of EARLIER_RELEASES) {
    const atTag = hashSkillsAtRef(ROOT, `v${release}`);
    assert.ok(Object.keys(atTag).length > 0, `no skills at v${release}`);
    for (const [skillId, hashed] of Object.entries(atTag)) {
      const entry = (baselines[skillId] || []).find((item) => item.release === release);
      assert.ok(entry, `missing baseline ${skillId}@${release}`);
      assert.equal(entry.revision, hashed.revision);
      assert.deepEqual(entry.files, hashed.files);
    }
  }
});

test('baselines: an untouched copy of each earlier Release is legacy, high provenance, and upgrades with no flag', () => {
  const catalog = getCatalog(ROOT);
  for (const release of EARLIER_RELEASES) {
    for (const skill of catalog.skills) {
      const tree = readSkillTreeAtRef(ROOT, `v${release}`, skill.id);
      if (!tree) continue;
      const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-baseline-legacy-'));
      try {
        const dest = path.join(projectRoot, '.agents', 'skills', skill.id);
        plantTree(dest, tree);
        if (computeSkillRevision(dest) === skill.revision) continue;

        const plan = createInstallPlan(catalog, { skillId: skill.id, projectRoot, packageRoot: ROOT, dryRun: true });
        assert.equal(plan.destinations[0].recognition, 'legacy', `${skill.id}@${release}`);
        assert.equal(plan.destinations[0].confidence, 'high', `${skill.id}@${release}`);

        executeProjectInstall({ catalog, skillId: skill.id, projectRoot, packageRoot: ROOT });
        assert.equal(computeSkillRevision(dest), skill.revision, `${skill.id}@${release} not upgraded`);
      } finally {
        fs.rmSync(projectRoot, { recursive: true, force: true });
      }
    }
  }
});

test('baselines: a changed copy of an earlier Release still needs an explicit choice', () => {
  const catalog = getCatalog(ROOT);
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-baseline-changed-'));
  try {
    const dest = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    plantTree(dest, readSkillTreeAtRef(ROOT, 'v0.3.0', 'sigmawrite'));
    fs.appendFileSync(path.join(dest, 'SKILL.md'), '\nmy local edit\n');
    const plan = createInstallPlan(catalog, { skillId: 'sigmawrite', projectRoot, packageRoot: ROOT, dryRun: true });
    assert.notEqual(plan.destinations[0].recognition, 'legacy');
    assert.throws(
      () => executeProjectInstall({ catalog, skillId: 'sigmawrite', projectRoot, packageRoot: ROOT }),
      /explicit replace, skip, or export/,
    );
    assert.match(fs.readFileSync(path.join(dest, 'SKILL.md'), 'utf8'), /my local edit/);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('baselines: plan labels files from the installer point of view', () => {
  const catalog = getCatalog(ROOT);
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-baseline-labels-'));
  try {
    const dest = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    fs.cpSync(path.join(ROOT, 'sigmawrite'), dest, { recursive: true });
    fs.rmSync(path.join(dest, 'agents', 'openai.yaml'));
    fs.writeFileSync(path.join(dest, 'extra.md'), 'local only', 'utf8');
    const plan = createInstallPlan(catalog, { skillId: 'sigmawrite', projectRoot, packageRoot: ROOT, dryRun: true });
    const { diff } = plan.destinations[0];
    assert.deepEqual(diff.added, ['agents/openai.yaml']);
    assert.deepEqual(diff.deleted, ['extra.md']);
    // A file the new Release adds is written, not replaced.
    assert.ok(plan.writes.includes('.agents/skills/sigmawrite/agents/openai.yaml'));
    assert.ok(!plan.replacements.includes('.agents/skills/sigmawrite/agents/openai.yaml'));
    assert.ok(plan.replacements.includes('.agents/skills/sigmawrite/SKILL.md'));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('baselines: release --write-identities appends the outgoing Release for every skill', () => {
  const rootDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-baseline-release-'));
  const git = (...args) => execFileSync('git', args, { cwd: rootDir, encoding: 'utf8' });
  try {
    git('init', '-q');
    git('config', 'user.email', 'test@example.com');
    git('config', 'user.name', 'Test');
    git('config', 'core.autocrlf', 'false');
    fs.writeFileSync(path.join(rootDir, 'package.json'), `${JSON.stringify({ name: 'x', version: '0.1.0' }, null, 2)}\n`);
    fs.writeFileSync(path.join(rootDir, 'manifest.json'), `${JSON.stringify({ version: '0.1.0', skills: [{ id: 'demo' }] }, null, 2)}\n`);
    fs.writeFileSync(path.join(rootDir, 'CHANGELOG.md'), '# Changelog\n\n## [Unreleased]\n\n## [0.1.0] — 2026-01-01\n\n### Added\n\n- First.\n');
    fs.mkdirSync(path.join(rootDir, 'demo'));
    fs.writeFileSync(path.join(rootDir, 'demo', 'SKILL.md'), '---\nname: demo\n---\nold\n');
    git('add', '-A');
    git('commit', '-q', '-m', 'v0.1.0');
    git('tag', 'v0.1.0');
    const outgoing = hashSkillsAtRef(rootDir, 'v0.1.0');

    fs.writeFileSync(path.join(rootDir, 'demo', 'SKILL.md'), '---\nname: demo\n---\nnew\n');
    fs.writeFileSync(path.join(rootDir, 'CHANGELOG.md'), '# Changelog\n\n## [Unreleased]\n\n### Fixed\n\n- Better.\n\n## [0.1.0] — 2026-01-01\n\n### Added\n\n- First.\n');
    writeReleaseIdentities(rootDir, { now: '2026-02-01T00:00:00Z' });

    // More changes after preparing identities must refresh the same unpublished candidate.
    const candidateLog = fs.readFileSync(path.join(rootDir, 'CHANGELOG.md'), 'utf8');
    fs.writeFileSync(path.join(rootDir, 'CHANGELOG.md'), candidateLog.replace('## [Unreleased]', '## [Unreleased]\n\n### Fixed\n\n- Another fix.'));
    const refreshed = writeReleaseIdentities(rootDir, { now: '2026-02-02T00:00:00Z' });
    assert.equal(refreshed.version, '0.1.1');
    assert.match(fs.readFileSync(path.join(rootDir, 'CHANGELOG.md'), 'utf8'), /Another fix/);
    assert.equal((fs.readFileSync(path.join(rootDir, 'CHANGELOG.md'), 'utf8').match(/## \[0\.1\.1\]/g) || []).length, 1);

    const written = JSON.parse(fs.readFileSync(path.join(rootDir, 'registry', 'skill-baselines.json'), 'utf8'));
    assert.deepEqual(written.skills.demo, [{ release: '0.1.0', ...outgoing.demo }]);

    // Running it again for the same outgoing Release adds nothing twice.
    fs.writeFileSync(path.join(rootDir, 'package.json'), `${JSON.stringify({ name: 'x', version: '0.1.0' }, null, 2)}\n`);
    fs.writeFileSync(path.join(rootDir, 'manifest.json'), `${JSON.stringify({ version: '0.1.0', skills: [{ id: 'demo' }] }, null, 2)}\n`);
    fs.writeFileSync(path.join(rootDir, 'CHANGELOG.md'), '# Changelog\n\n## [Unreleased]\n\n### Fixed\n\n- Better.\n\n## [0.1.0] — 2026-01-01\n\n### Added\n\n- First.\n');
    writeReleaseIdentities(rootDir, { now: '2026-02-01T00:00:00Z' });
    const again = JSON.parse(fs.readFileSync(path.join(rootDir, 'registry', 'skill-baselines.json'), 'utf8'));
    assert.equal(again.skills.demo.length, 1);
  } finally {
    fs.rmSync(rootDir, { recursive: true, force: true });
  }
});

test('baselines: release guidance names the baselines file among the files to commit', () => {
  const human = formatReleaseHuman({ identitiesCommitted: false, skills: [] });
  assert.match(human, /registry\/skill-baselines\.json/);
  const readme = fs.readFileSync(path.join(ROOT, 'README.md'), 'utf8');
  assert.match(readme, /`--write-identities` writes[^\n]*?skill hashes[^\n]*?`registry\/skill-baselines\.json`/);
});

test('baselines: personal links prevent automatic legacy replacement and appear in the preview', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-baseline-link-'));
  try {
    const dest = path.join(projectRoot, '.agents', 'skills', 'sigmareview');
    plantTree(dest, readSkillTreeAtRef(ROOT, 'v0.1.0', 'sigmareview'));
    const personal = path.join(projectRoot, 'personal');
    fs.mkdirSync(personal);
    fs.writeFileSync(path.join(personal, 'note.txt'), 'keep me');
    fs.symlinkSync(personal, path.join(dest, 'personal'), process.platform === 'win32' ? 'junction' : 'dir');
    const options = { catalog: getCatalog(ROOT), skillId: 'sigmareview', projectRoot, packageRoot: ROOT };
    const plan = createInstallPlan(options.catalog, options);
    assert.notEqual(plan.destinations[0].recognition, 'legacy');
    assert.ok(plan.destinations[0].diff.deleted.includes('personal'));
    assert.throws(() => executeProjectInstall(options), /explicit replace, skip, or export/);
    assert.ok(fs.lstatSync(path.join(dest, 'personal')).isSymbolicLink());
    assert.equal(fs.readFileSync(path.join(personal, 'note.txt'), 'utf8'), 'keep me');
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});
