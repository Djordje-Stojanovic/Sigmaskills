import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'os';
import path from 'node:path';
import test from 'node:test';
import {
  chooseCanonical,
  classifySkillPath,
  RECOGNITION_PRECEDENCE,
} from '../src/adoption.js';
import { getCatalog, findPackageRoot } from '../src/catalog.js';
import { recommendedLinkMethod } from '../src/links.js';
import { inspectProjectLock, loadProjectLock } from '../src/project-lock.js';
import { computeSkillRevision } from '../src/revision.js';

const ROOT = findPackageRoot();
const LINK_METHOD = recommendedLinkMethod();

function plantSkill(destDir, skillId = 'sigmawrite') {
  fs.mkdirSync(path.dirname(destDir), { recursive: true });
  fs.cpSync(path.join(ROOT, skillId), destDir, { recursive: true });
}

test('recognition precedence is valid Sigma state, then exact bundled revision, then recognized link target', () => {
  assert.deepEqual(RECOGNITION_PRECEDENCE, ['sigma-state', 'exact-revision', 'recognized-link']);
});

test('classify: valid Sigma state wins over an exact copy and a recognized link', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-adopt-prec-'));
  try {
    const catalog = getCatalog(ROOT);
    const revision = catalog.skills.find((skill) => skill.id === 'sigmawrite').revision;
    const canonical = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    const host = path.join(projectRoot, '.claude', 'skills', 'sigmawrite');
    plantSkill(canonical);
    fs.mkdirSync(path.dirname(host), { recursive: true });
    fs.symlinkSync(canonical, host, process.platform === 'win32' ? 'junction' : 'dir');

    const classified = classifySkillPath({
      destPath: host,
      bundledRevision: revision,
      expectedCanonicalPath: canonical,
      sigmaOwned: true,
      sigmaRevision: revision,
    });
    assert.equal(classified.kind, 'sigma-state');
    assert.equal(classified.adoptable, true);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('classify: exact bundled Skill Revision is adopted when Sigma state is absent', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-adopt-exact-'));
  try {
    const dest = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    plantSkill(dest);
    const revision = computeSkillRevision(dest);
    const classified = classifySkillPath({
      destPath: dest,
      bundledRevision: revision,
      expectedCanonicalPath: dest,
      sigmaOwned: false,
    });
    assert.equal(classified.kind, 'exact-revision');
    assert.equal(classified.method, 'copy');
    assert.equal(classified.revision, revision);
    assert.equal(classified.adoptable, true);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('classify: links and junctions are recognized by resolved target, not link text', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-adopt-link-'));
  try {
    const canonical = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    const host = path.join(projectRoot, '.claude', 'skills', 'sigmawrite');
    plantSkill(canonical);
    fs.mkdirSync(path.dirname(host), { recursive: true });
    const relativeText = process.platform === 'win32'
      ? canonical
      : path.relative(path.dirname(host), canonical);
    fs.symlinkSync(relativeText, host, process.platform === 'win32' ? 'junction' : 'dir');

    const revision = computeSkillRevision(canonical);
    const classified = classifySkillPath({
      destPath: host,
      bundledRevision: revision,
      expectedCanonicalPath: canonical,
      sigmaOwned: false,
    });
    assert.equal(classified.kind, 'recognized-link');
    assert.equal(classified.method, LINK_METHOD);
    assert.equal(fs.realpathSync(classified.resolvedTarget), fs.realpathSync(canonical));
    assert.equal(classified.adoptable, true);
    const rawTarget = fs.readlinkSync(host);
    assert.equal(path.resolve(path.dirname(host), rawTarget), fs.realpathSync(canonical));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('classify: foreign trees are not adoptable even when they look like a skill folder', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-adopt-foreign-'));
  try {
    const dest = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    fs.mkdirSync(dest, { recursive: true });
    fs.writeFileSync(path.join(dest, 'SKILL.md'), 'foreign content', 'utf8');
    const classified = classifySkillPath({
      destPath: dest,
      bundledRevision: 'abc',
      expectedCanonicalPath: dest,
      sigmaOwned: false,
    });
    assert.equal(classified.kind, 'foreign');
    assert.equal(classified.adoptable, false);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('generic skills-lock.json is ignored and never implies Sigma ownership', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-adopt-generic-lock-'));
  try {
    fs.writeFileSync(path.join(projectRoot, 'skills-lock.json'), `${JSON.stringify({
      skills: {
        sigmawrite: {
          source: 'npx',
          sourceUrl: 'https://example.invalid/other',
        },
        'acme/other-skill': {
          source: 'github',
        },
      },
    }, null, 2)}\n`);

    const inspected = inspectProjectLock(projectRoot);
    assert.equal(inspected.kind, 'generic');

    const lock = loadProjectLock(projectRoot);
    assert.equal(lock.release, null);
    assert.deepEqual(lock.skills, {});
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('duplicate exact destinations choose one canonical copy and report the fate of every other copy', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-adopt-dup-'));
  try {
    const canonical = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    const host = path.join(projectRoot, '.claude', 'skills', 'sigmawrite');
    plantSkill(canonical);
    plantSkill(host);
    const revision = computeSkillRevision(canonical);

    const decision = chooseCanonical([
      {
        relativeDestination: '.agents/skills/sigmawrite',
        relativeRoot: '.agents/skills',
        destPath: canonical,
        classification: classifySkillPath({
          destPath: canonical,
          bundledRevision: revision,
          expectedCanonicalPath: canonical,
          sigmaOwned: false,
        }),
      },
      {
        relativeDestination: '.claude/skills/sigmawrite',
        relativeRoot: '.claude/skills',
        destPath: host,
        classification: classifySkillPath({
          destPath: host,
          bundledRevision: revision,
          expectedCanonicalPath: canonical,
          sigmaOwned: false,
        }),
      },
    ]);

    assert.equal(decision.canonical.relativeDestination, '.agents/skills/sigmawrite');
    assert.equal(decision.canonical.fate, 'keep');
    assert.equal(decision.others.length, 1);
    assert.equal(decision.others[0].relativeDestination, '.claude/skills/sigmawrite');
    assert.equal(decision.others[0].fate, 'keep');
    assert.equal(decision.others[0].role, 'host');
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});
