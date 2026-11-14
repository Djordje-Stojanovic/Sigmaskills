import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { parseSkillFrontmatter } from '../src/catalog.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const KNOWN_SKILLS = [
  { id: 'sigmafreedom', title: 'SigmaFreedom', needsReferences: true },
  { id: 'sigmaloop', title: 'SigmaLoop', needsReferences: true },
  { id: 'sigmataste', title: 'SigmaTaste', needsReferences: true },
  { id: 'sigmahuman', title: 'SigmaHuman', needsReferences: true },
  { id: 'sigmatour', title: 'SigmaTour', needsReferences: true },
  { id: 'sigmaspeedloop', title: 'SigmaSpeedLoop', needsReferences: true },
  { id: 'sigmamusk', title: 'SigmaMusk', needsReferences: true },
  { id: 'sigmaboat', title: 'SigmaBoat', needsReferences: false },
  { id: 'sigmadebug', title: 'SigmaDebug', needsReferences: false },
  { id: 'sigmacreatearena', title: 'SigmaCreateArena', needsReferences: true },
  {
    id: 'sigmareview',
    title: 'SigmaReview',
    needsReferences: true,
  },
  {
    id: 'sigmaimprove',
    title: 'SigmaImprove',
    needsReferences: true,
  },
  {
    id: 'sigmabrief',
    title: 'SigmaBrief',
    needsReferences: true,
  },
  {
    id: 'sigmaship',
    title: 'SigmaShip',
    needsReferences: true,
  },
  {
    id: 'sigmawrite',
    title: 'SigmaWrite',
    needsReferences: false,
  },
  {
    id: 'sigmaresearch',
    title: 'SigmaResearch',
    needsReferences: true,
  },
  {
    id: 'sigmadeeplook',
    title: 'SigmaDeepLook',
    needsReferences: true,
  },
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

// The README ships in the npm package and shows on npmjs.com, so a relative link
// works only when its target ships too. Other targets need an absolute GitHub URL.
test('shipped text files hold no raw control bytes (a heredoc can turn \\b into a backspace)', () => {
  const textExt = new Set(['.py', '.js', '.mjs', '.md', '.txt', '.yaml', '.yml', '.json', '.html', '.css', '.sh', '.ps1']);
  const roots = [...listSkillDirs(), 'scripts', 'src', 'bin'];
  const bad = [];
  const walk = (rel) => {
    for (const entry of fs.readdirSync(path.join(ROOT, rel), { withFileTypes: true })) {
      const child = path.join(rel, entry.name);
      if (entry.isDirectory()) {
        if (entry.name !== 'node_modules' && entry.name !== '__pycache__') walk(child);
      } else if (textExt.has(path.extname(entry.name).toLowerCase())) {
        const bytes = fs.readFileSync(path.join(ROOT, child));
        const at = bytes.findIndex((b) => b < 0x20 && b !== 0x09 && b !== 0x0a && b !== 0x0d);
        if (at >= 0) bad.push(`${child}: byte 0x${bytes[at].toString(16).padStart(2, '0')} at offset ${at}`);
      }
    }
  };
  for (const root of roots) if (exists(root)) walk(root);
  assert.deepEqual(bad, []);
});

test('package.json is publishable, requires Node 22+, exposes bin, and defines files allowlist', () => {
  const pkg = JSON.parse(read('package.json'));
  assert.equal(pkg.name, '@djordje-stojanovic/sigmaskills');
  assert.equal(pkg.type, 'module');
  assert.equal(pkg.private, undefined, 'root package must be publishable (not private)');
  assert.equal(pkg.engines?.node, '>=22', 'requires Node.js 22+');
  assert.equal(pkg.bin?.sigmaskills, 'bin/sigmaskills.js', 'exposes sigmaskills binary');
  assert.ok(Array.isArray(pkg.files), 'package.json must specify explicit files allowlist');
  assert.ok(pkg.files.includes('bin'));
  assert.ok(pkg.files.includes('src'));
  assert.ok(pkg.files.includes('manifest.json'));
  for (const skill of KNOWN_SKILLS) {
    assert.ok(pkg.files.includes(skill.id), `package.json files allowlist missing ${skill.id}`);
  }
  assert.match(pkg.scripts.test, /node scripts\/run-tests\.js/);
  assert.doesNotMatch(pkg.scripts.test, /\*\*/, 'Node 20 does not expand ** globs in npm test');
});

test('manifest.json agrees with KNOWN_SKILLS and discovered skills', () => {
  assert.ok(exists('manifest.json'), 'missing manifest.json');
  const manifest = JSON.parse(read('manifest.json'));
  assert.equal(manifest.schemaVersion, 1);
  assert.equal(manifest.name, 'sigmaskills');
  assert.equal(manifest.version, JSON.parse(read('package.json')).version);
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

const CODEX_PRODUCTS = ['chatgpt', 'codex', 'atlas'];

function yamlProducts(yaml) {
  const block = yaml.match(/products:\s*\n((?:\s+-\s*\S+\s*\n)+)/);
  assert.ok(block, 'openai.yaml needs a products list');
  return [...block[1].matchAll(/-\s*(\S+)/g)].map((m) => m[1]);
}

test('every openai.yaml lists only products that Codex knows', () => {
  for (const skill of KNOWN_SKILLS) {
    const products = yamlProducts(read(path.join(skill.id, 'agents', 'openai.yaml')));
    for (const product of products) {
      assert.ok(CODEX_PRODUCTS.includes(product), `${skill.id}: unknown product "${product}" (allowed: ${CODEX_PRODUCTS.join(', ')})`);
    }
  }
});

test('skill names and descriptions follow the Agent Skills limits', () => {
  for (const skill of KNOWN_SKILLS) {
    const { name, description } = parseFrontmatter(read(path.join(skill.id, 'SKILL.md')));
    assert.match(name, /^[a-z0-9]+(-[a-z0-9]+)*$/, `${skill.id}: name must be lowercase letters, digits, and single hyphens`);
    assert.ok(name.length <= 64, `${skill.id}: name is over 64 characters`);
    assert.ok(description.length <= 1024, `${skill.id}: description has ${description.length} characters (max 1024)`);
  }
});

test('every SKILL.md header is strict YAML: a plain description never holds ": "', () => {
  for (const skill of KNOWN_SKILLS) {
    const raw = read(path.join(skill.id, 'SKILL.md')).match(/^description:[ 	]*(.*)$/m)[1].trim();
    const quoted = /^'.*'$/.test(raw) || /^".*"$/.test(raw);
    assert.ok(quoted || !raw.includes(': '), `${skill.id}: quote the description; a plain YAML value cannot contain ": "`);
  }
});

function githubSlug(heading) {
  return heading
    .trim()
    .toLowerCase()
    .replace(/[`*_~]/g, '')
    .replace(/[^\p{L}\p{N}\s-]/gu, '')
    .replace(/\s/g, '-');
}

function headingSlugs(md) {
  const seen = new Map();
  const slugs = new Set();
  let fence = false;
  for (const line of md.split(/\r?\n/)) {
    if (/^\s*(```|~~~)/.test(line)) fence = !fence;
    const m = !fence && line.match(/^#{1,6}\s+(.+?)\s*#*\s*$/);
    if (!m) continue;
    const base = githubSlug(m[1].replace(/\[([^\]]*)\]\([^)]*\)/g, '$1'));
    const n = seen.get(base) ?? 0;
    seen.set(base, n + 1);
    slugs.add(n === 0 ? base : `${base}-${n}`);
  }
  return slugs;
}

function walkFiles(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    return entry.isDirectory() ? walkFiles(full) : [full];
  });
}

function brokenLinks(file) {
  const problems = [];
  let fence = false;
  const lines = fs.readFileSync(file, 'utf8').split(/\r?\n/);
  for (const line of lines) {
    if (/^\s*(```|~~~)/.test(line)) fence = !fence;
    if (fence) continue;
    const text = line.replace(/`[^`]*`/g, '');
    for (const m of text.matchAll(/\[[^\]]*\]\(([^)\s]+)\)/g)) {
      const href = m[1];
      if (/^[a-z][a-z0-9+.-]*:/i.test(href)) continue;
      const [rel, anchor] = href.split('#');
      const target = rel === '' ? file : path.resolve(path.dirname(file), decodeURIComponent(rel));
      if (!fs.existsSync(target)) {
        problems.push(`${path.relative(ROOT, file)}: ${href} does not exist`);
      } else if (anchor && target.endsWith('.md') && !headingSlugs(fs.readFileSync(target, 'utf8')).has(anchor)) {
        problems.push(`${path.relative(ROOT, file)}: ${href} has no matching heading`);
      }
    }
  }
  return problems;
}

test('link checker finds a missing file and a missing heading', () => {
  const tmp = fs.mkdtempSync(path.join(ROOT, 'test', 'link-check-'));
  try {
    fs.writeFileSync(path.join(tmp, 'a.md'), '# Top\n\n[ok](b.md#real-one) [bad](b.md#nope) [gone](c.md) [self](#top)\n');
    fs.writeFileSync(path.join(tmp, 'b.md'), '## Real one\n');
    assert.deepEqual(
      brokenLinks(path.join(tmp, 'a.md')).map((p) => p.replace(/^.*?: /, '')),
      ['b.md#nope has no matching heading', 'c.md does not exist'],
    );
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
});

test('every relative link and anchor in the skill folders resolves', () => {
  const problems = KNOWN_SKILLS.flatMap((skill) =>
    walkFiles(path.join(ROOT, skill.id))
      .filter((f) => f.endsWith('.md'))
      .flatMap(brokenLinks),
  );
  assert.deepEqual(problems, []);
});

// The owner's private repositories, hosts and paths never ship in the public package.
const PRIVATE_PARTS = /Thinkcenter_Setup|Design_Experiments|geldtools|lazy_toolkits|\bCT100\b|storgestudio|StorgeStudio/i;

test('no tracked file outside the history names a private repository, host or path', () => {
  const skip = new Set(['CHANGELOG.md', 'ENGINEERING.md', 'AGENTS.md', 'registry/skill-baselines.json', 'test/repo-invariants.test.js', 'test/sigmawrite-gui.test.js']);
  const files = execFileSync('git', ['ls-files'], { cwd: ROOT, encoding: 'utf8' }).split('\n').filter(Boolean)
    .filter((f) => !skip.has(f) && !f.startsWith('docs/audits/') && !/\.(png|jpe?g|gif|webp|ico|woff2?|pdf|mp4|wav)$/i.test(f));
  const hits = files.filter((f) => fs.existsSync(path.join(ROOT, f)) && PRIVATE_PARTS.test(fs.readFileSync(path.join(ROOT, f), 'utf8')));
  assert.deepEqual(hits, []);
});
