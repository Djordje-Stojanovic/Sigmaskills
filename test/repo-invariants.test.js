import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { parseSkillFrontmatter } from '../src/catalog.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const KNOWN_SKILLS = [
  {
    id: 'sigmareview',
    title: 'SigmaReview',
    needsReferences: true,
  },
  {
    id: 'sigmaperformance',
    title: 'SigmaPerformance',
    needsReferences: true,
  },
  {
    id: 'sigmabrief',
    title: 'SigmaBrief',
    needsReferences: true,
  },
  {
    id: 'sigmawrite',
    title: 'SigmaWrite',
    needsReferences: false,
  },
];

const ISSUE_TEMPLATES = [
  'ISSUE_TEMPLATE/config.yml',
  'ISSUE_TEMPLATE/01-bug-report.yml',
  'ISSUE_TEMPLATE/02-feature-request.yml',
  'ISSUE_TEMPLATE/03-improvement.yml',
  'ISSUE_TEMPLATE/04-docs.yml',
  'pull_request_template.md',
];

function read(rel) {
  return fs.readFileSync(path.join(ROOT, rel), 'utf8');
}

function exists(rel) {
  return fs.existsSync(path.join(ROOT, rel));
}

function listSkillDirs() {
  return fs
    .readdirSync(ROOT, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name)
    .filter((name) => exists(path.join(name, 'SKILL.md')))
    .sort();
}

function parseFrontmatter(md) {
  return parseSkillFrontmatter(md);
}



function wordCount(text) {
  return text.split(/\s+/).filter(Boolean).length;
}

test('repo ships required root docs and license', () => {
  for (const file of [
    'README.md',
    'CHANGELOG.md',
    'LICENSE',
    'package.json',
    'AGENTS.md',
  ]) {
    assert.ok(exists(file), `missing ${file}`);
  }
  const changelog = read('CHANGELOG.md');
  assert.match(changelog, /## \[0\.1\.0\]/);
  assert.match(read('LICENSE'), /MIT/);
});

test('AGENTS.md teaches registry discipline and SigmaWrite voice', () => {
  const agents = read('AGENTS.md');
  assert.match(agents, /KNOWN_SKILLS/);
  assert.match(agents, /test\/repo-invariants\.test\.js/);
  assert.match(agents, /CI fails on purpose/i);
  assert.match(agents, /SigmaWrite|sigmawrite/);
  assert.match(agents, /npm test/);
  assert.doesNotMatch(agents, /maximum\s+\d+\s+words/i);
});

test('discovered skill folders match the known registry', () => {
  const found = listSkillDirs();
  const expected = KNOWN_SKILLS.map((s) => s.id).sort();
  assert.deepEqual(
    found,
    expected,
    `skill folders drifted.\nfound: ${found.join(', ')}\nexpected: ${expected.join(', ')}\nUpdate KNOWN_SKILLS in test/repo-invariants.test.js and README together.`,
  );
});

test('each skill has valid SKILL.md and openai.yaml', () => {
  for (const skill of KNOWN_SKILLS) {
    const skillMd = read(path.join(skill.id, 'SKILL.md'));
    const { name, description, body } = parseFrontmatter(skillMd);

    assert.equal(name, skill.id, `${skill.id}: frontmatter name must match folder`);
    assert.ok(description.length > 40, `${skill.id}: description too short`);
    assert.match(description, /Do not use/i, `${skill.id}: description should include “Do not use” negatives`);
    assert.match(body, new RegExp(`^# ${skill.title}\\s*$`, 'm'), `${skill.id}: body needs H1 “# ${skill.title}”`);

    const yamlPath = path.join(skill.id, 'agents', 'openai.yaml');
    assert.ok(exists(yamlPath), `${skill.id}: missing agents/openai.yaml`);
    const yaml = read(yamlPath);
    assert.match(yaml, new RegExp(`display_name:\\s*${skill.title}\\b`));
    assert.match(yaml, new RegExp(`\\$${skill.id}\\b`), `${skill.id}: default_prompt should mention $${skill.id}`);
    assert.match(yaml, /allow_implicit_invocation:\s*(true|false)/);

    if (skill.needsReferences) {
      const refDir = path.join(ROOT, skill.id, 'references');
      assert.ok(fs.existsSync(refDir), `${skill.id}: expected references/`);
      const refs = fs.readdirSync(refDir).filter((f) => f.endsWith('.md'));
      assert.ok(refs.length >= 1, `${skill.id}: references/ should contain markdown`);
    }
  }
});

test('README wires every skill for install and run', () => {
  const readme = read('README.md');

  assert.match(readme, /npx skills add Djordje-Stojanovic\/Sigmaskills --all/);
  assert.match(readme, /v0\.1\.0/);
  assert.match(readme, /CHANGELOG\.md/);

  for (const skill of KNOWN_SKILLS) {
    assert.match(readme, new RegExp(`### ${skill.title}\\b`));
    assert.match(
      readme,
      new RegExp(`npx skills add[^\\n]*--skill ${skill.id}`),
      `README missing npx --skill ${skill.id}`,
    );
    assert.match(
      readme,
      new RegExp(`\\$skill-installer install ${skill.id} from`),
      `README missing Codex installer for ${skill.id}`,
    );
    assert.match(
      readme,
      new RegExp(`(?:cp -R|Copy-Item)[^\\n]*${skill.id}`),
      `README missing manual copy for ${skill.id}`,
    );
    assert.match(readme, new RegExp(`\\$${skill.id}\\b`), `README missing $${skill.id} invoke example`);
    assert.match(readme, new RegExp(`/skill:${skill.id}\\b`), `README missing /skill:${skill.id} example`);
  }
});

test('CHANGELOG mentions every shipped skill id', () => {
  const changelog = read('CHANGELOG.md');
  for (const skill of KNOWN_SKILLS) {
    assert.match(changelog, new RegExp(`\`${skill.id}\``), `CHANGELOG missing \`${skill.id}\``);
  }
});

test('GitHub issue kit templates remain present', () => {
  for (const rel of ISSUE_TEMPLATES) {
    assert.ok(exists(path.join('.github', rel)), `missing .github/${rel}`);
  }
  assert.match(read('.github/ISSUE_TEMPLATE/config.yml'), /blank_issues_enabled:\s*false/);
});

test('SigmaWrite stays soft-steer and Karpathy-sized', () => {
  const { body } = parseFrontmatter(read('sigmawrite/SKILL.md'));
  const words = wordCount(body);
  assert.ok(words >= 200, `sigmawrite body too thin (${words} words)`);
  assert.ok(words <= 400, `sigmawrite body too long (${words} words); keep near Karpathy length`);

  assert.match(body, /Paste as system prompt/i);
  assert.match(body, /From now on/i);
  assert.match(body, /Never/i);

  // Hard numbered writing laws must not creep back in.
  assert.doesNotMatch(body, /maximum\s+\d+\s+words/i);
  assert.doesNotMatch(body, /max(?:imum)?\s+\d+\s+words/i);
  assert.doesNotMatch(body, /no more than\s+\d+\s+words/i);
  assert.doesNotMatch(body, /^\s*\d+\.\s+Use only approved words/im);
});

test('package.json is publishable, requires Node 20+, exposes bin, and defines files allowlist', () => {
  const pkg = JSON.parse(read('package.json'));
  assert.equal(pkg.name, 'sigmaskills');
  assert.equal(pkg.type, 'module');
  assert.equal(pkg.private, undefined, 'root package must be publishable (not private)');
  assert.match(pkg.engines?.node, />=\s*20/, 'requires Node.js 20+');
  assert.equal(pkg.bin?.sigmaskills, './bin/sigmaskills.js', 'exposes sigmaskills binary');
  assert.ok(Array.isArray(pkg.files), 'package.json must specify explicit files allowlist');
  assert.ok(pkg.files.includes('bin'));
  assert.ok(pkg.files.includes('src'));
  assert.ok(pkg.files.includes('manifest.json'));
  for (const skill of KNOWN_SKILLS) {
    assert.ok(pkg.files.includes(skill.id), `package.json files allowlist missing ${skill.id}`);
  }
  assert.match(pkg.scripts.test, /node --test/);
});

test('manifest.json agrees with KNOWN_SKILLS and discovered skills', () => {
  assert.ok(exists('manifest.json'), 'missing manifest.json');
  const manifest = JSON.parse(read('manifest.json'));
  assert.equal(manifest.schemaVersion, 1);
  assert.equal(manifest.name, 'sigmaskills');
  assert.equal(manifest.version, '0.1.0');
  assert.ok(Array.isArray(manifest.skills));

  const manifestIds = manifest.skills.map((s) => s.id).sort();
  const knownIds = KNOWN_SKILLS.map((s) => s.id).sort();
  const diskIds = listSkillDirs();

  assert.deepEqual(manifestIds, knownIds, 'manifest.json skills must match KNOWN_SKILLS');
  assert.deepEqual(manifestIds, diskIds, 'manifest.json skills must match on-disk skill folders');
});

test('every shipped skill contains approved Personal instructions customization block', () => {
  for (const skill of KNOWN_SKILLS) {
    const skillMd = read(path.join(skill.id, 'SKILL.md'));
    assert.match(
      skillMd,
      /## Personal instructions\s*\r?\n\r?\n<sigmaskills-custom>[\s\S]*?<\/sigmaskills-custom>/,
      `${skill.id}: missing or malformed ## Personal instructions block`,
    );

    // Verify tag counts
    const startCount = (skillMd.match(/<sigmaskills-custom>/g) || []).length;
    const endCount = (skillMd.match(/<\/sigmaskills-custom>/g) || []).length;
    assert.equal(startCount, 1, `${skill.id}: must have exactly 1 start tag`);
    assert.equal(endCount, 1, `${skill.id}: must have exactly 1 end tag`);
  }
});

