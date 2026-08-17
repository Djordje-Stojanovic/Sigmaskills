import assert from 'node:assert/strict';
import { execFileSync, execSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { exportSkillTree } from '../src/backup.js';
import { getCatalog, findPackageRoot } from '../src/catalog.js';
import { CUSTOM_BLOCK_END, CUSTOM_BLOCK_START, extractCustomContent, injectCustomContent } from '../src/customization.js';
import { createInstallPlan, formatPlanHuman } from '../src/plan.js';
import { loadProjectLock, PROJECT_LOCK_FILENAME } from '../src/project-lock.js';
import { getProjectStateDir, loadProjectState, STATE_FILENAME } from '../src/state.js';
import { executeProjectInstall } from '../src/transaction.js';

const ROOT = findPackageRoot();

function plantSkill(destDir, skillId = 'sigmawrite') {
  fs.mkdirSync(path.dirname(destDir), { recursive: true });
  fs.cpSync(path.join(ROOT, skillId), destDir, { recursive: true });
}

function skillBytes(destDir) {
  const files = {};
  const walk = (dir, prefix = '') => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full, rel);
      else files[rel] = fs.readFileSync(full);
    }
  };
  walk(destDir);
  return files;
}

function stripCustomization(markdown) {
  const heading = markdown.indexOf('## Personal instructions');
  if (heading === -1) return `${markdown.trimEnd()}\n\nUser note that must not be guessed.\n`;
  return `${markdown.slice(0, heading).trimEnd()}\n\nUser note that must not be guessed.\n`;
}

test('plan: dry-run shows additions, replacements, deletions, and low provenance before mutation', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-legacy-plan-'));
  try {
    const dest = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    plantSkill(dest);
    fs.writeFileSync(path.join(dest, 'extra.md'), 'local extra', 'utf8');
    const skillMd = path.join(dest, 'SKILL.md');
    fs.writeFileSync(skillMd, `${fs.readFileSync(skillMd, 'utf8')}\n`);

    const catalog = getCatalog(ROOT);
    const plan = createInstallPlan(catalog, {
      skillId: 'sigmawrite',
      projectRoot,
      packageRoot: ROOT,
      dryRun: true,
    });

    assert.equal(plan.destinations[0].recognition, 'unverified');
    assert.equal(plan.destinations[0].confidence, 'low');
    assert.ok(plan.destinations[0].diff.added.includes('extra.md'));
    assert.equal(plan.requiresApproval, true);
    const human = formatPlanHuman(plan);
    assert.match(human, /Additions:\s+extra\.md/);
    assert.match(human, /Provenance:\s+low/);
    assert.equal(fs.readFileSync(path.join(dest, 'extra.md'), 'utf8'), 'local extra');
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: replace commits a private backup then writes the bundled tree', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-legacy-replace-'));
  try {
    const dest = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    plantSkill(dest);
    fs.writeFileSync(path.join(dest, 'extra.md'), 'keep in backup', 'utf8');
    const before = skillBytes(dest);

    const catalog = getCatalog(ROOT);
    const result = executeProjectInstall({
      catalog,
      skillId: 'sigmawrite',
      projectRoot,
      packageRoot: ROOT,
      adoptUnverified: 'replace',
    });

    assert.equal(result.plan.destinations[0].resolution, 'replace');
    assert.ok(!fs.existsSync(path.join(dest, 'extra.md')));
    const backupRoot = path.join(getProjectStateDir(projectRoot), 'backups', 'sigmawrite');
    const stamps = fs.readdirSync(backupRoot);
    assert.equal(stamps.length, 1);
    assert.deepEqual(skillBytes(path.join(backupRoot, stamps[0])), before);
    assert.ok(!fs.existsSync(path.join(path.dirname(dest), `.sigmawrite-backup`)));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: skip leaves unverified bytes and does not claim ownership', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-legacy-skip-'));
  try {
    const dest = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    plantSkill(dest);
    fs.writeFileSync(path.join(dest, 'extra.md'), 'stay', 'utf8');
    const before = skillBytes(dest);

    const catalog = getCatalog(ROOT);
    executeProjectInstall({
      catalog,
      skillId: 'sigmawrite',
      projectRoot,
      packageRoot: ROOT,
      adoptUnverified: 'skip',
    });

    assert.deepEqual(skillBytes(dest), before);
    assert.ok(!fs.existsSync(path.join(projectRoot, PROJECT_LOCK_FILENAME)));
    const statePath = path.join(projectRoot, '.agents', STATE_FILENAME);
    assert.ok(!fs.existsSync(statePath) || !loadProjectState(projectRoot).skills.sigmawrite);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: export uses a collision-safe destination and rolls back partial output', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-legacy-export-'));
  try {
    const dest = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    plantSkill(dest);
    fs.writeFileSync(path.join(dest, 'extra.md'), 'exported', 'utf8');
    const exportRoot = path.join(projectRoot, 'exports');
    fs.mkdirSync(path.join(exportRoot, 'sigmawrite'), { recursive: true });
    fs.writeFileSync(path.join(exportRoot, 'sigmawrite', 'occupied.txt'), 'taken', 'utf8');

    const catalog = getCatalog(ROOT);
    const result = executeProjectInstall({
      catalog,
      skillId: 'sigmawrite',
      projectRoot,
      packageRoot: ROOT,
      adoptUnverified: 'export',
      exportDir: exportRoot,
    });

    assert.ok(fs.existsSync(path.join(exportRoot, 'sigmawrite-2', 'extra.md')));
    assert.equal(result.plan.destinations[0].exportPath, path.join(exportRoot, 'sigmawrite-2'));
    assert.match(formatPlanHuman(result.plan), /Export:\s+/);
    assert.ok(fs.existsSync(path.join(dest, 'extra.md')));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('exportSkillTree rolls back partial output when the copy fails', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-export-rollback-'));
  try {
    const exportRoot = path.join(projectRoot, 'exports');
    fs.mkdirSync(exportRoot, { recursive: true });
    assert.throws(
      () => exportSkillTree({
        sourceDir: path.join(projectRoot, 'missing-skill'),
        exportRoot,
        skillId: 'sigmawrite',
      }),
      /failed to export/,
    );
    assert.deepEqual(
      fs.readdirSync(exportRoot).filter((name) => name.startsWith('.sigma-export') || name.startsWith('sigmawrite')),
      [],
    );
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: pre-marker extra content is not guessed into the customization block', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-legacy-premarker-'));
  try {
    const dest = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    plantSkill(dest);
    const skillMd = path.join(dest, 'SKILL.md');
    fs.writeFileSync(skillMd, stripCustomization(fs.readFileSync(skillMd, 'utf8')), 'utf8');

    const catalog = getCatalog(ROOT);
    executeProjectInstall({
      catalog,
      skillId: 'sigmawrite',
      projectRoot,
      packageRoot: ROOT,
      adoptUnverified: 'replace',
    });

    const installed = fs.readFileSync(skillMd, 'utf8');
    assert.ok(!installed.includes('User note that must not be guessed'));
    assert.equal(extractCustomContent(installed, 'sigmawrite').trim(), '');
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: valid customization is preserved on replace; malformed markers stop without a choice', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-legacy-custom-'));
  try {
    const dest = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    plantSkill(dest);
    const skillMd = path.join(dest, 'SKILL.md');
    const official = fs.readFileSync(skillMd, 'utf8');
    fs.writeFileSync(skillMd, injectCustomContent(official, 'Always prefer tables.\n', 'sigmawrite'), 'utf8');

    const catalog = getCatalog(ROOT);
    executeProjectInstall({
      catalog,
      skillId: 'sigmawrite',
      projectRoot,
      packageRoot: ROOT,
      adoptUnverified: 'replace',
    });
    assert.equal(extractCustomContent(fs.readFileSync(skillMd, 'utf8'), 'sigmawrite'), 'Always prefer tables.\n');

    fs.writeFileSync(skillMd, official.replace('<sigmaskills-custom>', '<sigmaskills-custom>\n<sigmaskills-custom>'), 'utf8');
    assert.throws(
      () => {
        executeProjectInstall({
          catalog,
          skillId: 'sigmawrite',
          projectRoot,
          packageRoot: ROOT,
        });
      },
      /explicit replace, skip, or export/,
    );
    assert.match(fs.readFileSync(skillMd, 'utf8'), /<sigmaskills-custom>\n<sigmaskills-custom>/);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: duplicate changed paths each receive an explicit resolution', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-legacy-dups-'));
  try {
    const canonical = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    const host = path.join(projectRoot, '.claude', 'skills', 'sigmawrite');
    plantSkill(canonical);
    plantSkill(host);
    fs.writeFileSync(path.join(canonical, 'one.md'), 'a', 'utf8');
    fs.writeFileSync(path.join(host, 'two.md'), 'b', 'utf8');

    const catalog = getCatalog(ROOT);
    const result = executeProjectInstall({
      catalog,
      skillId: 'sigmawrite',
      projectRoot,
      packageRoot: ROOT,
      selectedRoots: ['.agents/skills', '.claude/skills'],
      method: 'copy',
      resolutions: {
        '.agents/skills/sigmawrite': 'replace',
        '.claude/skills/sigmawrite': 'skip',
      },
    });

    assert.equal(result.plan.adoption.copies.find((copy) => copy.destination === '.agents/skills/sigmawrite').fate, 'replace');
    assert.equal(result.plan.adoption.copies.find((copy) => copy.destination === '.claude/skills/sigmawrite').fate, 'skip');
    assert.ok(!fs.existsSync(path.join(canonical, 'one.md')));
    assert.ok(fs.existsSync(path.join(host, 'two.md')));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: failure after backup or after state change restores the prior tree', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-legacy-fail-'));
  try {
    const dest = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    plantSkill(dest);
    fs.writeFileSync(path.join(dest, 'extra.md'), 'original', 'utf8');
    const before = skillBytes(dest);
    const catalog = getCatalog(ROOT);

    assert.throws(
      () => {
        executeProjectInstall({
          catalog,
          skillId: 'sigmawrite',
          projectRoot,
          packageRoot: ROOT,
          adoptUnverified: 'replace',
          afterBackup: () => {
            throw new Error('fail after backup');
          },
        });
      },
      /fail after backup/,
    );
    assert.deepEqual(skillBytes(dest), before);
    const backupRoot = path.join(getProjectStateDir(projectRoot), 'backups', 'sigmawrite');
    assert.ok(!fs.existsSync(backupRoot) || fs.readdirSync(backupRoot).length === 0);

    assert.throws(
      () => {
        executeProjectInstall({
          catalog,
          skillId: 'sigmawrite',
          projectRoot,
          packageRoot: ROOT,
          adoptUnverified: 'replace',
          saveState: () => {
            throw new Error('fail after state');
          },
        });
      },
      /fail after state/,
    );
    assert.deepEqual(skillBytes(dest), before);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('packed CLI classifies, backups, and exports changed Sigma-looking trees', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-pack-legacy-'));
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
    const installedBin = path.join(appDir, 'node_modules', 'sigmaskills', 'bin', 'sigmaskills.js');
    const packedRoot = path.join(appDir, 'node_modules', 'sigmaskills');

    const project = path.join(tmpDir, 'proj');
    const dest = path.join(project, '.agents', 'skills', 'sigmawrite');
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.cpSync(path.join(packedRoot, 'sigmawrite'), dest, { recursive: true });
    fs.writeFileSync(path.join(dest, 'extra.md'), 'packed extra', 'utf8');

    const dry = execFileSync(
      'node',
      [installedBin, 'install', 'sigmawrite', '--project', project, '--dry-run', '--json'],
      { cwd: appDir, encoding: 'utf8' },
    );
    const dryPlan = JSON.parse(dry);
    assert.equal(dryPlan.destinations[0].recognition, 'unverified');
    assert.equal(dryPlan.destinations[0].confidence, 'low');
    assert.ok(dryPlan.destinations[0].diff.added.includes('extra.md'));

    execFileSync(
      'node',
      [
        installedBin, 'install', 'sigmawrite',
        '--project', project,
        '--adopt-unverified', 'replace',
      ],
      { cwd: appDir, encoding: 'utf8' },
    );
    assert.ok(!fs.existsSync(path.join(dest, 'extra.md')));
    const backups = fs.readdirSync(path.join(project, '.agents', 'backups', 'sigmawrite'));
    assert.equal(backups.length, 1);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});
