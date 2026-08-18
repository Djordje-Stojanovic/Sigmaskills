import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { getCatalog, findPackageRoot } from '../src/catalog.js';
import { runCli } from '../src/cli.js';
import { injectCustomContent } from '../src/customization.js';
import {
  UNIVERSAL_PROJECT_DESTINATION,
  listProjectDestinationGroups,
  loadHostRegistry,
} from '../src/destinations.js';
import { pathExists, removeManagedPath } from '../src/links.js';
import { collectStatus, formatStatusHuman, STATUS_SCHEMA_VERSION } from '../src/status.js';
import { executeProjectInstall } from '../src/transaction.js';

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
      if (stat.isDirectory() && !stat.isSymbolicLink()) {
        walk(full);
      } else if (stat.isSymbolicLink()) {
        files[rel] = `link:${fs.readlinkSync(full)}`;
      } else {
        files[rel] = crypto.createHash('sha256').update(fs.readFileSync(full)).digest('hex');
      }
    }
  };
  walk(root);
  return files;
}

function destOf(report, relativeDestination) {
  for (const skill of report.skills) {
    const found = skill.destinations.find((dest) => dest.relativeDestination === relativeDestination);
    if (found) return found;
  }
  return null;
}

function kindsOf(report, relativeDestination) {
  return destOf(report, relativeDestination)?.classifications || [];
}

test('status: clean Project Installation reports scope, releases, revision, hosts, method, path, and ownership', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-status-clean-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const catalog = getCatalog(ROOT);
    const report = collectStatus({
      catalog,
      projectRoot,
      packageRoot: ROOT,
      scope: 'project',
    });

    assert.equal(report.schemaVersion, STATUS_SCHEMA_VERSION);
    assert.equal(report.command, 'status');
    assert.equal(report.scope, 'project');
    assert.equal(report.release.running, catalog.manifest.version);
    assert.equal(report.release.installed, catalog.manifest.version);
    assert.equal(report.drift, false);

    const skill = report.skills.find((item) => item.id === 'sigmawrite');
    assert.ok(skill);
    assert.equal(skill.runningRevision, catalog.skills.find((item) => item.id === 'sigmawrite').revision);
    assert.equal(skill.installedRevision, skill.runningRevision);
    assert.equal(skill.corruption, false);

    const dest = destOf(report, '.agents/skills/sigmawrite');
    assert.equal(dest.owned, true);
    assert.equal(dest.method, 'copy');
    assert.ok(dest.absolutePath.endsWith(path.join('.agents', 'skills', 'sigmawrite')));
    assert.ok(dest.hostIds.length > 0);
    assert.deepEqual(dest.classifications, ['clean']);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('status: valid Skill Customization is drift without corruption', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-status-custom-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const skillMd = path.join(projectRoot, '.agents', 'skills', 'sigmawrite', 'SKILL.md');
    const next = injectCustomContent(fs.readFileSync(skillMd, 'utf8'), 'Prefer short answers.\n');
    fs.writeFileSync(skillMd, next, 'utf8');

    const report = collectStatus({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      scope: 'project',
    });
    const dest = destOf(report, '.agents/skills/sigmawrite');
    assert.equal(report.drift, true);
    assert.equal(report.skills[0].corruption, false);
    assert.ok(dest.classifications.includes('valid-customization'));
    assert.ok(!dest.classifications.includes('outside-change'));
    assert.ok(!dest.classifications.includes('clean'));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('status: classifies outside edits, extra and missing resources, and malformed markers', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-status-drift-'));
  try {
    installWrite(projectRoot, 'sigmareview');
    const destDir = path.join(projectRoot, '.agents', 'skills', 'sigmareview');
    const skillMd = path.join(destDir, 'SKILL.md');
    fs.writeFileSync(skillMd, `${fs.readFileSync(skillMd, 'utf8')}\nOutside the markers.\n`, 'utf8');
    fs.writeFileSync(path.join(destDir, 'notes.md'), 'local note', 'utf8');
    const resource = fs.readdirSync(path.join(destDir, 'references'))[0];
    fs.rmSync(path.join(destDir, 'references', resource));

    const report = collectStatus({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      scope: 'project',
    });
    const kinds = kindsOf(report, '.agents/skills/sigmareview');
    assert.ok(kinds.includes('outside-change'));
    assert.ok(kinds.includes('outside-addition'));
    assert.ok(kinds.includes('missing-resource'));
    assert.ok(!kinds.includes('extra-resource'));
    assert.ok(!kinds.includes('outside-deletion'));
    assert.equal(report.skills[0].corruption, true);

    fs.writeFileSync(skillMd, '# broken\n<sigmaskills-custom>\n', 'utf8');
    const malformed = collectStatus({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      scope: 'project',
    });
    assert.ok(kindsOf(malformed, '.agents/skills/sigmareview').includes('malformed-markers'));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('status: missing owned destination is stale state', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-status-missing-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    fs.rmSync(path.join(projectRoot, '.agents', 'skills', 'sigmawrite'), { recursive: true, force: true });
    const report = collectStatus({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      scope: 'project',
    });
    const kinds = kindsOf(report, '.agents/skills/sigmawrite');
    assert.ok(kinds.includes('missing-destination'));
    assert.ok(kinds.includes('stale-state'));
    assert.equal(report.drift, true);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('status: broken and wrong-target links are classified without following unowned targets', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-status-link-'));
  const foreign = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-status-foreign-'));
  try {
    installWrite(projectRoot, 'sigmawrite', {
      selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
      method: 'link',
    });
    fs.writeFileSync(path.join(foreign, 'FOREIGN.txt'), 'should-not-be-read', 'utf8');
    const host = path.join(projectRoot, '.claude', 'skills', 'sigmawrite');
    removeManagedPath(host);
    fs.symlinkSync(foreign, host, process.platform === 'win32' ? 'junction' : 'dir');

    const report = collectStatus({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      scope: 'project',
    });
    const hostDest = destOf(report, '.claude/skills/sigmawrite');
    assert.ok(hostDest.classifications.includes('wrong-target'));
    assert.ok(!Object.keys(hostDest.files || {}).includes('FOREIGN.txt'));
    assert.ok(!JSON.stringify(report).includes('FOREIGN.txt'));
    assert.ok(!JSON.stringify(report).includes('should-not-be-read'));

    removeManagedPath(host);
    fs.symlinkSync(path.join(projectRoot, 'missing-target'), host, process.platform === 'win32' ? 'junction' : 'dir');
    const broken = collectStatus({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      scope: 'project',
    });
    assert.ok(kindsOf(broken, '.claude/skills/sigmawrite').includes('broken-link'));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
    fs.rmSync(foreign, { recursive: true, force: true });
  }
});

test('status: independent copies that disagree are classified', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-status-copies-'));
  try {
    installWrite(projectRoot, 'sigmawrite', {
      selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
      method: 'copy',
    });
    fs.writeFileSync(path.join(projectRoot, '.claude', 'skills', 'sigmawrite', 'extra.md'), 'only here', 'utf8');
    const report = collectStatus({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      scope: 'project',
    });
    const host = destOf(report, '.claude/skills/sigmawrite');
    const canonical = destOf(report, '.agents/skills/sigmawrite');
    assert.ok(host.classifications.includes('copy-disagreement'));
    assert.ok(canonical.classifications.includes('copy-disagreement'));
    assert.ok(host.classifications.includes('outside-addition'));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('status: Global Installation reports global scope without writing a project lock', () => {
  const homeDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-status-global-'));
  try {
    executeProjectInstall({
      catalog: getCatalog(ROOT),
      skillId: 'sigmawrite',
      scope: 'global',
      homeDir,
      packageRoot: ROOT,
      env: { ...process.env, HOME: homeDir, USERPROFILE: homeDir },
    });
    const before = snapshotTree(homeDir);
    const report = collectStatus({
      catalog: getCatalog(ROOT),
      homeDir,
      packageRoot: ROOT,
      scope: 'global',
      env: { ...process.env, HOME: homeDir, USERPROFILE: homeDir },
    });
    assert.equal(report.scope, 'global');
    assert.equal(report.drift, false);
    assert.ok(!fs.existsSync(path.join(homeDir, 'skills-lock.json')));
    assert.deepEqual(snapshotTree(homeDir), before);
    assert.deepEqual(destOf(report, '.agents/skills/sigmawrite').classifications, ['clean']);
  } finally {
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});

test('cli: status --json is versioned, exits 0 on drift, and is byte-for-byte read-only offline', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-status-cli-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    fs.writeFileSync(path.join(projectRoot, '.agents', 'skills', 'sigmawrite', 'extra.md'), 'drift', 'utf8');
    const before = snapshotTree(projectRoot);
    const io = createMockIo({
      ...process.env,
      HOME: projectRoot,
      USERPROFILE: projectRoot,
      http_proxy: 'http://127.0.0.1:9',
      https_proxy: 'http://127.0.0.1:9',
      HTTP_PROXY: 'http://127.0.0.1:9',
      HTTPS_PROXY: 'http://127.0.0.1:9',
      NO_PROXY: '*',
    });
    const code = await runCli(['status', '--json', '--project', projectRoot], io);
    const after = snapshotTree(projectRoot);

    assert.equal(code, 0);
    assert.deepEqual(after, before);
    const parsed = JSON.parse(io.getStdout());
    assert.equal(parsed.schemaVersion, STATUS_SCHEMA_VERSION);
    assert.equal(parsed.command, 'status');
    assert.equal(parsed.scope, 'project');
    assert.equal(parsed.drift, true);
    assert.equal(parsed.readOnly, true);
    assert.equal(io.getStderr(), '');
    const statusSource = fs.readFileSync(path.join(ROOT, 'src', 'status.js'), 'utf8');
    assert.doesNotMatch(statusSource, /\b(fetch|http|https|net|undici|dns)\b/);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('cli: status human output names scope, release, paths, and ownership; command failure is exit 1', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-status-human-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const io = createMockIo();
    const code = await runCli(['status', '--project', projectRoot], io);
    assert.equal(code, 0);
    const out = io.getStdout();
    assert.match(out, /Project Installation/);
    assert.match(out, /Scope:\s+project/);
    assert.match(out, /Release:/);
    assert.match(out, /\.agents\/skills\/sigmawrite/);
    assert.match(out, /Owned:/);
    assert.match(out, /clean/);
    assert.equal(formatStatusHuman(JSON.parse(JSON.stringify({
      schemaVersion: 1,
      command: 'status',
      scope: 'project',
      release: { installed: '0.1.0', running: '0.1.0' },
      drift: false,
      skills: [],
    }))).includes('Project Installation'), true);

    const badRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-status-bad-'));
    try {
      fs.mkdirSync(path.join(badRoot, '.agents'), { recursive: true });
      fs.writeFileSync(path.join(badRoot, '.agents', 'state.json'), '{not-json', 'utf8');
      const failIo = createMockIo();
      const failCode = await runCli(['status', '--project', badRoot], failIo);
      assert.equal(failCode, 1);
      assert.match(failIo.getStderr(), /sigmaskills error:/);
    } finally {
      fs.rmSync(badRoot, { recursive: true, force: true });
    }
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});
