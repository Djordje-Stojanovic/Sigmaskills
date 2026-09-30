import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { parseSkillFrontmatter } from '../src/catalog.js';
import { CHECKOUT_ACTION_PIN, SETUP_NODE_ACTION_PIN } from '../scripts/release.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const KNOWN_SKILLS = [
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
    id: 'sigmarefactor',
    title: 'SigmaRefactor',
    needsReferences: true,
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
  assert.match(agents, /\(docs\/installer\.md\)/, 'AGENTS.md must point at the installer guide');
  assert.match(agents, /\(docs\/maintainers\.md\)/, 'AGENTS.md must point at the maintainer guide');
  assert.doesNotMatch(agents, /output contracts for every host/i, 'AGENTS.md describes the old README');
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

test('README and the installer guide wire every skill for install and run', () => {
  const pkg = JSON.parse(read('package.json'));
  const readme = read('README.md');
  const guide = read('docs/installer.md');

  assert.match(readme, /npx skills add Djordje-Stojanovic\/Sigmaskills --all/);
  assert.match(readme, new RegExp(`v${pkg.version.replaceAll('.', '\\.')}`));
  assert.match(readme, /CHANGELOG\.md/);
  assert.match(
    readme,
    /\(https:\/\/github\.com\/Djordje-Stojanovic\/Sigmaskills\/blob\/main\/docs\/installer\.md\)/,
    'README must link the installer guide',
  );

  for (const skill of KNOWN_SKILLS) {
    assert.match(readme, new RegExp(`### ${skill.title}\\b`));
    assert.match(
      guide,
      new RegExp(`npx skills add[^\\n]*--skill ${skill.id}`),
      `docs/installer.md missing npx --skill ${skill.id}`,
    );
    assert.match(
      guide,
      new RegExp(`\\$skill-installer install ${skill.id} from`),
      `docs/installer.md missing Codex installer for ${skill.id}`,
    );
    assert.match(
      guide,
      new RegExp(`(?:cp -R|Copy-Item)[^\\n]*${skill.id}`),
      `docs/installer.md missing manual copy for ${skill.id}`,
    );
    assert.match(readme, new RegExp(`\\$${skill.id}\\b`), `README missing $${skill.id} invoke example`);
    assert.match(readme, new RegExp(`/skill:${skill.id}\\b`), `README missing /skill:${skill.id} example`);
  }
});

// The README ships in the npm package and shows on npmjs.com, so a relative link
// works only when its target ships too. Other targets need an absolute GitHub URL.
test('README relative links point only at files in the npm package', () => {
  const pkg = JSON.parse(read('package.json'));
  const readme = read('README.md');
  const targets = [...readme.matchAll(/\]\(([^)\s]+)\)/g)]
    .map((match) => match[1])
    .filter((target) => !/^(?:[a-z]+:|#)/i.test(target));
  assert.ok(targets.length > 0, 'expected relative links such as CHANGELOG.md');
  for (const target of targets) {
    const top = target.split('#')[0].split('/')[0];
    assert.ok(pkg.files.includes(top), `README link '${target}' is not in the npm package; use an absolute GitHub URL`);
  }
});

// Counting rule: fenced code blocks, table rows, and HTML tags do not count.
// A paragraph is a block between blank lines; each list item is its own paragraph.
// A word is a whitespace-separated token with at least one letter or digit.
function proseWords(text) {
  return text.split(/\s+/).filter((token) => /[\p{L}\p{N}]/u.test(token)).length;
}

function proseOf(md) {
  return md
    .replace(/^```[\s\S]*?^```[^\n]*$/gm, '')
    .split(/\r?\n/)
    .filter((line) => !/^\s*\|/.test(line))
    .map((line) => line.replace(/<[^>]+>/g, ''))
    .join('\n');
}

function paragraphsOf(prose) {
  return prose
    .split(/\n\s*\n/)
    .flatMap((block) => block.split(/\n(?=\s*(?:[-*]|\d+\.)\s)/))
    .map((p) => p.trim())
    .filter(Boolean);
}

test('README word counter skips code, tables, and HTML, and splits list items', () => {
  const md = 'One two.\n\n```bash\nnot counted\n```\n\n| a | b |\n|---|---|\n\n<td>three</td>\n\n- four\n- five six\n';
  const prose = proseOf(md);
  assert.equal(proseWords(prose), 6);
  assert.deepEqual(paragraphsOf(prose), ['One two.', 'three', '- four', '- five six']);
});

test('README stays short: under 1,500 words and no paragraph over 80 words', () => {
  const prose = proseOf(read('README.md'));
  const words = proseWords(prose);
  assert.ok(words < 1500, `README has ${words} prose words; keep it under 1,500 and move details to docs/`);
  for (const paragraph of paragraphsOf(prose)) {
    const n = proseWords(paragraph);
    assert.ok(n <= 80, `README paragraph has ${n} words (max 80): ${paragraph.slice(0, 60)}…`);
  }
});

test('CHANGELOG mentions every shipped skill id', () => {
  const changelog = read('CHANGELOG.md');
  for (const skill of KNOWN_SKILLS) {
    assert.match(changelog, new RegExp(`\`${skill.id}\``), `CHANGELOG missing \`${skill.id}\``);
  }
});

test('CI covers Node.js 22 and 24 on Windows, macOS, and Linux, and no older Node.js', () => {
  const ci = read('.github/workflows/ci.yml');
  assert.match(ci, /os:\s*\[ubuntu-latest,\s*windows-latest,\s*macos-latest\]/);
  assert.match(ci, /node-version:\s*\[22,\s*24\]/);
  assert.doesNotMatch(ci, /node-version:\s*20\b/, 'Node 20 is not supported');
  assert.match(ci, /npm test/);
  assert.match(ci, /sigma-test-fs/);
  assert.match(ci, /fetch-depth: 0/);
});

test('CI reads the repository only, pins actions by SHA, and rehearses the Release path', () => {
  const ci = read('.github/workflows/ci.yml');
  assert.match(ci, /\npermissions:\s*\n\s+contents: read\s*\n/);
  assert.doesNotMatch(ci, /: write|id-token|secrets\.|environment:|npm publish/);
  const uses = [...ci.matchAll(/uses:\s*(\S+)(.*)/g)];
  assert.ok(uses.length > 0);
  for (const [, action, comment] of uses) {
    assert.match(action, /@[a-f0-9]{40}$/, `${action} must be pinned by full commit SHA`);
    assert.match(comment, /#\s*v\d+\.\d+\.\d+/, `${action} needs a # vX.Y.Z comment`);
  }
  assert.match(ci, new RegExp(`actions/checkout@${CHECKOUT_ACTION_PIN}`));
  assert.match(ci, new RegExp(`actions/setup-node@${SETUP_NODE_ACTION_PIN}`));
  assert.match(ci, /release-rehearsal:[\s\S]*github\.event\.pull_request\.head\.sha[\s\S]*node \.\/scripts\/release-rehearsal\.js/);
});

test('release, registry, and rehearsal jobs share one Node LTS line, need no npm upgrade, and have timeouts', () => {
  const ci = read('.github/workflows/ci.yml');
  const release = read('.github/workflows/release.yml');
  const registry = read('.github/workflows/registry-sync.yml');
  const rehearsal = ci.match(/release-rehearsal:[\s\S]*?node-version:\s*'([^']+)'/)[1];
  assert.equal(rehearsal, '24', 'release jobs track the latest Node 24 LTS, so the pin never goes stale');
  for (const [name, text] of [['release', release], ['registry-sync', registry]]) {
    const versions = [...text.matchAll(/node-version:\s*'([^']+)'/g)].map((m) => m[1]);
    assert.ok(versions.length > 0, `${name}.yml pins Node`);
    for (const v of versions) assert.equal(v, rehearsal, `${name}.yml must use the rehearsal Node`);
    assert.doesNotMatch(text, /npm install -g npm@/, `${name}.yml must not install npm on its own`);
    const jobs = (text.match(/^ {4}runs-on:/gm) || []).length;
    assert.equal((text.match(/^ {4}timeout-minutes:\s*\d+/gm) || []).length, jobs, `${name}.yml jobs need timeout-minutes`);
  }
});

test('no bot opens recurring pull requests: no Dependabot and no registry-sync schedule', () => {
  assert.equal(fs.existsSync(path.join(ROOT, '.github', 'dependabot.yml')), false, 'action pins are bumped at release time');
  const registry = read('.github/workflows/registry-sync.yml');
  assert.doesNotMatch(registry, /^\s*schedule:/m, 'registry sync runs on demand before a Release');
  assert.match(registry, /workflow_dispatch:/);
  assert.doesNotMatch(registry, /required:\s*true/, 'dispatch inputs are optional');
});

test('bug template and PR template cover the installer CLI', () => {
  const bug = read('.github/ISSUE_TEMPLATE/01-bug-report.yml');
  assert.match(bug, /Sigma Installer \(CLI\)/);
  for (const id of ['cli-version', 'node-version', 'os']) assert.match(bug, new RegExp(`id: ${id}(?:\\s|$)`));
  const pr = read('.github/pull_request_template.md');
  assert.match(pr, /- \[ \] `npm test` passes/);
  assert.match(pr, /- \[ \] CHANGELOG `\[Unreleased\]`/);
  assert.match(pr, /installer CLI/);
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

test('SigmaBrief is explicit-only in every host', () => {
  assert.match(read('sigmabrief/agents/openai.yaml'), /allow_implicit_invocation:\s*false/);
});

test('skill names and descriptions follow the Agent Skills limits', () => {
  for (const skill of KNOWN_SKILLS) {
    const { name, description } = parseFrontmatter(read(path.join(skill.id, 'SKILL.md')));
    assert.match(name, /^[a-z0-9]+(-[a-z0-9]+)*$/, `${skill.id}: name must be lowercase letters, digits, and single hyphens`);
    assert.ok(name.length <= 64, `${skill.id}: name is over 64 characters`);
    assert.ok(description.length <= 1024, `${skill.id}: description has ${description.length} characters (max 1024)`);
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

test('skills name one grilling skill and no private tools', () => {
  const files = KNOWN_SKILLS.flatMap((skill) => walkFiles(path.join(ROOT, skill.id))).filter((f) => f.endsWith('.md'));
  for (const file of [...files, path.join(ROOT, 'README.md')]) {
    const text = fs.readFileSync(file, 'utf8');
    const rel = path.relative(ROOT, file);
    assert.doesNotMatch(text, /Thinkcenter_Setup/, `${rel} names a private repository`);
    assert.doesNotMatch(text, /grill-me/, `${rel} must call the grilling skill /grilling`);
  }
});

test('README lists the optional companion skills and says laloc is optional', () => {
  const readme = read('README.md');
  for (const name of ['to-spec', 'to-tickets', 'grilling', 'tdd']) {
    assert.match(readme, new RegExp(`\`/${name}\``), `README requirements should list /${name}`);
  }
  assert.match(readme, /mattpocock\/skills/);
  assert.match(readme, /laloc[^\n]*(optional|if you have)/i);
});

test('SigmaShip and SigmaBrief agree on git and review rules', () => {
  const brief = [
    'sigmabrief/SKILL.md',
    'sigmabrief/references/brief-method.md',
    'sigmabrief/references/prompt-contract.md',
  ].map(read).join('\n');
  const ship = ['sigmaship/SKILL.md', 'sigmaship/references/review-round.md', 'sigmaship/references/land.md']
    .map(read)
    .join('\n');
  assert.doesNotMatch(brief, /(?<!never )\brebase\b/i, 'SigmaBrief must merge the base branch, not rebase a pushed branch');
  assert.doesNotMatch(brief, /git branch -d\b/, 'SigmaBrief must use git branch -D after a confirmed merge');
  assert.doesNotMatch(brief, /origin\/main|latest `?main`?/, 'SigmaBrief must say <base>, not hard-code main');
  assert.match(ship, /\/grilling/);
  assert.match(ship, /by hand/i, 'SigmaShip needs a fallback when companion skills are missing');
  assert.match(read('sigmaship/references/review-round.md'), /CLEAN \| FIXED \| BLOCKED[\s\S]*wins/i);
  assert.doesNotMatch(read('sigmaship/references/review-round.md'), /P1 \(a criterion fails/);
  assert.match(read('sigmaship/references/review-round.md'), /P1 \(a primary journey is broken, insecure, or breaks its budget\)/);
  assert.match(read('README.md'), /shell native to the machine/i);
  assert.match(read('sigmaship/SKILL.md'), /shell native to the (executing )?machine/i, 'SigmaShip needs the shell rule the changelog promises');
  assert.doesNotMatch(read('sigmaship/references/land.md'), /```(bash|sh)\b/, 'land.md commands must be shell-neutral');
  assert.match(read('sigmaship/SKILL.md'), /\/tdd/, 'README says SigmaShip works best with /tdd');
});

test('SigmaBrief examples follow its own dispatch format', () => {
  const contract = read('sigmabrief/references/prompt-contract.md');
  const lines = contract.split(/\r?\n/).filter((l) => /\|\s*isolation:/.test(l) && !/^\s*wave N/.test(l));
  for (const line of lines) {
    assert.match(line, /^wave \d+ \| .+ \| isolation: (on|off|ask) \| type: (greenfield|finish-PR|skip|blocked|session)\s*$/, `bad dispatch example: ${line}`);
  }
  assert.ok(lines.length >= 3, 'expected dispatch examples in the contract');
  assert.doesNotMatch(contract, /Open WebUI|Symfonium|CrowdSec|C:\AI\RepoName/i, 'examples must be generic');
});
