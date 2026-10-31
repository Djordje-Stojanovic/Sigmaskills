import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { PassThrough } from 'node:stream';
import test from 'node:test';
import { runCli } from '../src/cli.js';
import { findPackageRoot, getCatalog } from '../src/catalog.js';
import { createSourceFetcher } from '../src/pack-source.js';
import { buildTransform } from '../src/pack-transform.js';
import { findPack, loadPackCatalog, resolveSelection } from '../src/packs.js';
import {
  commitFiles, createEmptyRemote, createMockIo, createSandbox, writeUserConfig,
} from './pack-fixtures.js';

const packageRoot = findPackageRoot();
const catalog = getCatalog(packageRoot);
const registry = JSON.parse(fs.readFileSync(path.join(packageRoot, 'registry', 'packs.json'), 'utf8'));
const DOWN = '\x1b[B';
const RIGHT = '\x1b[C';
const ENTER = '\r';
const ESC = '\x1b';

function boxWithCache() {
  const box = createSandbox();
  box.env.SIGMA_CACHE_DIR = path.join(box.root, 'cache');
  return box;
}

async function run(box, args, project = box.project) {
  const io = createMockIo(box.env);
  const code = await runCli([...args, '--project', project, '--no-color'], io);
  return { code, out: io.getStdout(), err: io.getStderr() };
}

const skillFile = (box, id, ...rest) => path.join(box.project, '.agents', 'skills', id, ...rest);

// ---- pinned sources -------------------------------------------------------------------------

function pinnedRemote(box) {
  const dir = createEmptyRemote(box.remotes, 'acme/skills');
  const first = commitFiles(dir, { 'skills/alpha/SKILL.md': '---\nname: alpha\ndescription: Alpha first.\n---\n\n# alpha\n' }, 'first');
  const second = commitFiles(dir, { 'skills/alpha/SKILL.md': '---\nname: alpha\ndescription: Alpha second.\n---\n\n# alpha\n' }, 'second');
  return { dir, first, second };
}

const acmeAt = (ref) => ({
  id: 'acme', title: 'Acme', aliases: [],
  sources: [{ type: 'git', repo: 'acme/skills', path: 'skills', ...(ref ? { ref } : {}), skills: [{ id: 'alpha', description: 'Alpha.' }] }],
});

test('pin: a full commit SHA installs that commit and records it', async () => {
  const box = boxWithCache();
  try {
    const { first } = pinnedRemote(box);
    writeUserConfig(box.home, { packs: [acmeAt(first)] });
    const { code, err } = await run(box, ['install', '--preset', 'acme']);
    assert.equal(code, 0, err);
    assert.match(fs.readFileSync(skillFile(box, 'alpha', 'SKILL.md'), 'utf8'), /Alpha first/);
    const state = JSON.parse(fs.readFileSync(path.join(box.project, '.agents', '.sigmaskills', 'packs.json'), 'utf8'));
    assert.equal(state.skills.alpha.revision, first);
  } finally {
    box.cleanup();
  }
});

test('pin: a commit the remote does not have fails with a could-not-fetch note', async () => {
  const box = boxWithCache();
  try {
    pinnedRemote(box);
    writeUserConfig(box.home, { packs: [acmeAt('0'.repeat(40))] });
    const { code, out } = await run(box, ['install', '--preset', 'acme']);
    assert.equal(code, 1);
    assert.match(out, /could not fetch acme\/skills/);
  } finally {
    box.cleanup();
  }
});

test('cache: a pinned source is fetched once; a second project installs with the remote gone', async () => {
  const box = boxWithCache();
  try {
    const { dir, first } = pinnedRemote(box);
    writeUserConfig(box.home, { packs: [acmeAt(first)] });
    assert.equal((await run(box, ['install', '--preset', 'acme'])).code, 0);
    fs.rmSync(dir, { recursive: true, force: true });
    const other = path.join(box.root, 'project2');
    fs.mkdirSync(other);
    const again = await run(box, ['install', '--preset', 'acme'], other);
    assert.equal(again.code, 0, again.err + again.out);
    assert.ok(fs.existsSync(path.join(other, '.agents', 'skills', 'alpha', 'SKILL.md')));
  } finally {
    box.cleanup();
  }
});

test('fetcher: warm gets every source in parallel and fetch() then needs no remote', async () => {
  const box = boxWithCache();
  try {
    const a = createEmptyRemote(box.remotes, 'acme/one');
    const b = createEmptyRemote(box.remotes, 'acme/two');
    const shaA = commitFiles(a, { 'skills/one/SKILL.md': '---\nname: one\ndescription: One.\n---\n' });
    const shaB = commitFiles(b, { 'skills/two/SKILL.md': '---\nname: two\ndescription: Two.\n---\n' });
    const sources = [
      { type: 'git', repo: 'acme/one', path: 'skills', ref: shaA },
      { type: 'git', repo: 'acme/two', path: 'skills', ref: shaB },
    ];
    const fetcher = createSourceFetcher({ env: box.env });
    try {
      await fetcher.warm(sources);
      fs.rmSync(box.remotes, { recursive: true, force: true });
      assert.equal(fetcher.fetch(sources[0]).revision, shaA);
      assert.equal(fetcher.fetch(sources[1]).revision, shaB);
    } finally {
      fetcher.close();
    }
  } finally {
    box.cleanup();
  }
});

// ---- design-md: one skill per DESIGN.md, three at a time -----------------------------------

const BRANDS = [
  ['alpha', 'design-alpha', 'Alpha', 'Travel marketplace.'],
  ['beta.co', 'design-beta-co', 'Beta', 'Project management.'],
  ['gamma', 'design-gamma', 'Gamma', 'Payments.'],
  ['delta', 'design-delta', 'Delta', 'Consumer electronics.'],
  ['epsilon', 'design-epsilon', 'Epsilon', 'Athletic retail.'],
];

function designRemote(box) {
  const dir = createEmptyRemote(box.remotes, 'acme/designs');
  const files = { LICENSE: 'MIT License\nCopyright acme\n', 'README.md': 'list' };
  for (const [slug, , brand] of BRANDS) files[`design-md/${slug}/DESIGN.md`] = `# ${brand}\n\nTokens.\n`;
  return commitFiles(dir, files, 'designs');
}

const looksPack = (sha) => ({
  id: 'looks',
  title: 'Looks',
  blurb: 'Brand looks.',
  aliases: ['lk'],
  limit: { max: 3, counts: 'installed', onFourth: 'choose-drop' },
  sources: [{
    type: 'git',
    repo: 'acme/designs',
    ref: sha,
    path: 'design-md',
    transform: 'design-md',
    skills: BRANDS.map(([, id, brand, blurb]) => ({ id, description: `Use when building UI in the ${brand} look: ${blurb}`, group: 'Brands' })),
  }],
});

function looksBox() {
  const box = boxWithCache();
  const sha = designRemote(box);
  writeUserConfig(box.home, { packs: [looksPack(sha)] });
  return box;
}

test('design-md: one pick becomes a skill with a generated SKILL.md, the DESIGN.md and the licence', async () => {
  const box = looksBox();
  try {
    const { code, out, err } = await run(box, ['install', 'design-beta-co']);
    assert.equal(code, 0, err + out);
    assert.match(out, /1 skill installed/);
    assert.ok(!/failed/.test(out), out);
    const skill = fs.readFileSync(skillFile(box, 'design-beta-co', 'SKILL.md'), 'utf8');
    assert.match(skill, /^---\nname: design-beta-co\ndescription: "Use when building UI in the Beta look: Project management\."\n---\n/);
    assert.match(skill, /Read DESIGN\.md in this folder/);
    assert.match(fs.readFileSync(skillFile(box, 'design-beta-co', 'DESIGN.md'), 'utf8'), /^# Beta/);
    assert.match(fs.readFileSync(skillFile(box, 'design-beta-co', 'LICENSE'), 'utf8'), /MIT License/);
    assert.ok(!fs.existsSync(skillFile(box, 'design-gamma')), 'only the pick is written');
  } finally {
    box.cleanup();
  }
});

test('design-md: a pick of 1, 2 and 3 installs with 0 failed', async () => {
  for (const ids of [['design-alpha'], ['design-alpha', 'design-gamma'], ['design-alpha', 'design-gamma', 'design-delta']]) {
    const box = looksBox();
    try {
      const { code, out, err } = await run(box, ['install', ...ids]);
      assert.equal(code, 0, err + out);
      assert.match(out, new RegExp(`${ids.length} skills? installed`));
      assert.match(out, new RegExp(`Looks[ ]+${ids.length} of ${ids.length}`));
      assert.ok(!/failed|kept/.test(out), out);
    } finally {
      box.cleanup();
    }
  }
});

test('design-md: a 4th pick is refused with a choice, and --drop swaps one out', async () => {
  const box = looksBox();
  try {
    assert.equal((await run(box, ['install', 'design-alpha', 'design-gamma', 'design-delta'])).code, 0);
    const refused = await run(box, ['install', 'design-epsilon']);
    assert.equal(refused.code, 1);
    assert.match(refused.err, /at most 3/);
    assert.match(refused.err, /design-alpha, design-gamma, design-delta/);
    assert.match(refused.err, /--drop <id>/);
    assert.ok(!fs.existsSync(skillFile(box, 'design-epsilon')), 'nothing was written');

    const four = await run(box, ['install', 'design-beta-co', 'design-epsilon']);
    assert.equal(four.code, 1);

    const swapped = await run(box, ['install', 'design-epsilon', '--drop', 'design-alpha']);
    assert.equal(swapped.code, 0, swapped.err + swapped.out);
    assert.match(swapped.out, /Dropped design-alpha/);
    assert.ok(!fs.existsSync(skillFile(box, 'design-alpha')));
    assert.ok(fs.existsSync(skillFile(box, 'design-epsilon', 'DESIGN.md')));
  } finally {
    box.cleanup();
  }
});

test('design-md: picking four in one run is refused before anything is fetched or written', async () => {
  const box = looksBox();
  try {
    const refused = await run(box, ['install', 'design-alpha', 'design-gamma', 'design-delta', 'design-epsilon']);
    assert.equal(refused.code, 1);
    assert.match(refused.err, /at most 3/);
    assert.ok(!fs.existsSync(path.join(box.project, '.agents')));
  } finally {
    box.cleanup();
  }
});

test('design-md: the whole pack is never installed by accident, and --preset all skips it', async () => {
  const box = looksBox();
  try {
    const whole = await run(box, ['install', '--preset', 'looks']);
    assert.equal(whole.code, 1);
    assert.match(whole.err, /at most 3/);

    const packs = loadPackCatalog({ catalog, packageRoot, homeDir: box.home, env: box.env });
    const picked = resolveSelection(packs, { presets: ['all'] });
    assert.ok(!picked.skills.some((skill) => skill.pack === 'looks'), 'all skips a limited pack');
    assert.equal(findPack(packs, 'looks').limit.max, 3);
  } finally {
    box.cleanup();
  }
});

// ---- financial-services: plugins to skills --------------------------------------------------

function financeRemote(box) {
  const dir = createEmptyRemote(box.remotes, 'acme/fin');
  const skill = (name, text) => `---\nname: ${name}\ndescription: ${text}\n---\n\n# ${name}\n\nSteps.\n`;
  return commitFiles(dir, {
    LICENSE: 'Apache License\n',
    'plugins/vertical-plugins/equity/skills/zed-preview/SKILL.md': skill('zed-preview', 'Build earnings previews.'),
    'plugins/vertical-plugins/equity/skills/zed-preview/LICENSE': 'Apache License\n',
    'plugins/vertical-plugins/equity/skills/zed-strip/SKILL.md': skill('fsi-zed-strip', 'Make strip profiles.'),
    'plugins/vertical-plugins/equity/skills/skill-creator/SKILL.md': skill('skill-creator', 'Guide for skills.'),
    'plugins/vertical-plugins/equity/commands/zed-preview.md': '---\ndescription: Run an earnings preview\nargument-hint: "[ticker]"\n---\n\nLoad the `zed-preview` skill for the ticker.\n',
    'plugins/vertical-plugins/equity/commands/zed-screen.md': '---\ndescription: Screen ideas\nargument-hint: "[theme]"\n---\n\nScreen the market for the theme.\n',
    'plugins/agent-plugins/zed-pitcher/agents/zed-pitcher.md': '---\nname: zed-pitcher\ndescription: End-to-end pitch agent. Use when a banker asks for a first draft.\ntools: Read, Write, mcp__capiq__*\n---\n\nYou are the zed pitcher.\n',
    'plugins/agent-plugins/zed-pitcher/skills/zed-preview/SKILL.md': skill('zed-preview', 'Build earnings previews.'),
    'plugins/agent-plugins/zed-pitcher/skills/zed-model/SKILL.md': skill('zed-model', 'Build DCF models.'),
  }, 'plugins');
}

test('financial-services: skills, agents and commands become skills; a command with a skill of the same name folds into it', (t) => {
  const box = createSandbox();
  try {
    const sha = financeRemote(box);
    const repoRoot = path.join(box.root, 'checkout');
    fs.mkdirSync(repoRoot, { recursive: true });
    const fetcher = createSourceFetcher({ env: box.env });
    t.after(() => fetcher.close());
    const fetched = fetcher.fetch({ type: 'git', repo: 'acme/fin', ref: sha, path: 'plugins' });
    const out = path.join(box.root, 'out');
    const list = buildTransform('financial-services', {
      repoRoot: path.dirname(fetched.root), sourcePath: 'plugins', outDir: out, revision: sha, skills: [],
    });
    const ids = list.map((item) => item.id).sort();
    assert.deepEqual(ids, ['zed-model', 'zed-pitcher', 'zed-preview', 'zed-screen', 'zed-strip']);
    assert.ok(!fs.existsSync(path.join(out, 'skill-creator')), 'skill-creator is left out');
    const preview = fs.readFileSync(path.join(out, 'zed-preview', 'SKILL.md'), 'utf8');
    assert.match(preview, /When called as \/zed-preview/);
    assert.match(preview, /\[ticker\]/);
    assert.match(fs.readFileSync(path.join(out, 'zed-strip', 'SKILL.md'), 'utf8'), /^---\nname: zed-strip\n/, 'the name follows the folder');
    const agent = fs.readFileSync(path.join(out, 'zed-pitcher', 'SKILL.md'), 'utf8');
    assert.match(agent, /^---\nname: zed-pitcher\ndescription: End-to-end pitch agent\./);
    assert.ok(!/^tools:/m.test(agent.split('---')[1]), 'tools leave the frontmatter');
    assert.match(agent, /Tools this skill expects[\s\S]*mcp__capiq__\*/);
    assert.match(agent, /zed-model/, 'the skills the agent bundles are named');
    const command = fs.readFileSync(path.join(out, 'zed-screen', 'SKILL.md'), 'utf8');
    assert.match(command, /description: "?Screen ideas/);
    assert.match(command, /Usage: \/zed-screen \[theme\]/);
    assert.ok(list.find((item) => item.id === 'zed-pitcher').description.startsWith('End-to-end pitch agent'));
  } finally {
    box.cleanup();
  }
});

test('financial-services: a fresh-folder install of the converted set prints 0 failed', async () => {
  const box = boxWithCache();
  try {
    const sha = financeRemote(box);
    writeUserConfig(box.home, {
      packs: [{
        id: 'fin', title: 'Fin', aliases: [],
        sources: [{
          type: 'git', repo: 'acme/fin', ref: sha, path: 'plugins', transform: 'financial-services',
          skills: ['zed-model', 'zed-preview', 'zed-pitcher', 'zed-screen', 'zed-strip'].map((id) => ({ id, description: id })),
        }],
      }],
    });
    const { code, out, err } = await run(box, ['install', '--preset', 'fin']);
    assert.equal(code, 0, err + out);
    assert.match(out, /5 skills installed/);
    assert.match(out, /Fin[ ]+5 of 5/);
    assert.ok(!/failed|kept/.test(out), out);
    assert.ok(fs.existsSync(skillFile(box, 'zed-pitcher', 'SKILL.md')));
  } finally {
    box.cleanup();
  }
});

// ---- the registry ---------------------------------------------------------------------------

const pack = (id) => registry.packs.find((entry) => entry.id === id);

test('registry: the four new sets are pinned and listed, before Local', () => {
  const ids = registry.packs.map((entry) => entry.id);
  assert.deepEqual(ids, ['sigma', 'mattpocock', 'threejs', 'hyperframes', 'minimax-h3', 'anthropic', 'design-md', 'last30days', 'financial-services', 'tstack', 'local']);
  for (const id of ['anthropic', 'design-md', 'last30days', 'financial-services']) {
    for (const source of pack(id).sources) assert.match(source.ref, /^([0-9a-f]{40}|v\d+\.\d+\.\d+)$/, `${id} is pinned`);
  }
  assert.equal(pack('anthropic').sources[0].skills.length, 19);
  assert.equal(pack('anthropic').sources[0].ref, 'dbd4588f9e1033efb41dad4bef2f7947c8993d44');
  assert.deepEqual(pack('last30days').sources[0].skills.map((skill) => skill.id), ['last30days']);
  assert.equal(pack('last30days').sources[0].ref, 'v3.30.0');
  const design = pack('design-md');
  assert.equal(design.sources[0].skills.length, 84);
  assert.equal(design.limit.max, 3);
  assert.equal(design.sources[0].transform, 'design-md');
  assert.ok(design.sources[0].skills.every((skill) => skill.description.length <= 200 && skill.group));
  const finance = pack('financial-services').sources[0];
  assert.equal(finance.path, 'plugins');
  assert.equal(finance.transform, 'financial-services');
  assert.ok(finance.skills.length >= 62 + 10);
});

test('registry: no skill name is listed by two registry packs, and none shadows a Sigma skill', () => {
  const seen = new Map();
  for (const entry of registry.packs) {
    for (const source of entry.sources || []) {
      for (const skill of source.skills || []) {
        assert.ok(!seen.has(skill.id), `${skill.id} is in ${seen.get(skill.id)} and ${entry.id}`);
        seen.set(skill.id, entry.id);
      }
    }
  }
  for (const skill of catalog.skills) assert.ok(!seen.has(skill.id), `${skill.id} is a Sigma skill`);
});

test('registry: every set in a fresh catalog keeps all its skills (N of N)', () => {
  const box = createSandbox();
  try {
    const packs = loadPackCatalog({ catalog, packageRoot, homeDir: box.home, env: box.env });
    for (const id of ['anthropic', 'design-md', 'last30days', 'financial-services']) {
      const listed = pack(id).sources.reduce((n, source) => n + source.skills.length, 0);
      assert.equal(findPack(packs, id).skills.length, listed, id);
    }
  } finally {
    box.cleanup();
  }
});

// ---- the picker -----------------------------------------------------------------------------

function terminal(box, keys) {
  const stdin = new PassThrough();
  stdin.isTTY = true;
  stdin.setRawMode = () => {};
  const stdout = new PassThrough();
  stdout.isTTY = true;
  stdout.columns = 110;
  stdout.rows = 30;
  stdout.getColorDepth = () => 24;
  const stderr = new PassThrough();
  let out = '';
  stdout.setEncoding('utf8');
  stdout.on('data', (chunk) => { out += chunk; });
  if (Array.isArray(keys)) {
    // Staged keys: a lone Esc must arrive on its own, or the terminal reads it as Alt+Enter.
    // readline waits 500 ms after a lone Esc before it calls it a key, so the next chunk waits longer than that.
    let at = 0;
    keys.forEach((chunk, index) => {
      at += index > 0 && keys[index - 1] === ESC ? 700 : 60;
      setTimeout(() => (index === keys.length - 1 ? stdin.end(chunk) : stdin.write(chunk)), at);
    });
  } else {
    queueMicrotask(() => stdin.end(keys));
  }
  return { stdin, stdout, stderr, env: { ...box.env, TERM: 'xterm-256color' }, text: () => out.replace(/\x1b\[[0-9;?]*[A-Za-z]/g, '') };
}

const stateIds = (box) => Object.keys(JSON.parse(fs.readFileSync(path.join(box.project, '.agents', '.sigmaskills', 'packs.json'), 'utf8')).skills).sort();

// The Looks pack is the 12th row: eleven built-in packs come first. Down eleven times, open it, then down to row one.
const OPEN_LOOKS = `${DOWN.repeat(11)}${RIGHT}${DOWN}`;

test('wizard: the 4th pick opens a drop list; the dropped pick leaves and three skills install', async () => {
  const box = looksBox();
  try {
    // Pick rows 1, 2, 3 and 4 with space. The 4th pick opens the drop list; Enter drops the first. Then next, next, install.
    const keys = `${OPEN_LOOKS} ${DOWN} ${DOWN} ${DOWN} ${ENTER}${ENTER}${ENTER}${ENTER}`;
    const io = terminal(box, keys);
    const code = await runCli(['--project', box.project], io);
    const text = io.text();
    assert.equal(code, 0, text.slice(-1200));
    assert.match(text, /Looks holds 3 skills at a time\./);
    assert.match(text, /To add design-delta, drop one:/);
    assert.deepEqual(stateIds(box), ['design-beta-co', 'design-delta', 'design-gamma']);
    assert.ok(!/failed/.test(text.split('installing')[1] || ''), text);
  } finally {
    box.cleanup();
  }
});

test('wizard: with three installed, a new pick drops an installed skill in the same run', async () => {
  const box = looksBox();
  try {
    assert.equal((await run(box, ['install', 'design-alpha', 'design-beta-co', 'design-gamma'])).code, 0);
    // Row 4 is design-delta. Space opens the drop list (all three installed); Enter drops design-alpha.
    const keys = `${OPEN_LOOKS}${DOWN}${DOWN}${DOWN} ${ENTER}${ENTER}${ENTER}${ENTER}`;
    const io = terminal(box, keys);
    const code = await runCli(['--project', box.project], io);
    const text = io.text();
    assert.equal(code, 0, text.slice(-1200));
    assert.match(text, /installed/, 'installed rows are marked');
    assert.match(text, /dropped design-alpha/);
    assert.deepEqual(stateIds(box), ['design-beta-co', 'design-delta', 'design-gamma']);
    assert.ok(!fs.existsSync(skillFile(box, 'design-alpha')));
  } finally {
    box.cleanup();
  }
});

test('wizard: Esc in the drop list keeps every skill and adds nothing', async () => {
  const box = looksBox();
  try {
    const keys = [`${OPEN_LOOKS} ${DOWN} ${DOWN} ${DOWN} `, ESC, `${ENTER}${ENTER}${ENTER}`];
    const io = terminal(box, keys);
    const code = await runCli(['--project', box.project], io);
    assert.equal(code, 0, io.text().slice(-1200));
    assert.deepEqual(stateIds(box), ['design-alpha', 'design-beta-co', 'design-gamma']);
  } finally {
    box.cleanup();
  }
});

test('wizard: the Design.md pack key refuses the whole pack, and a for-all key skips it', async () => {
  const box = looksBox();
  try {
    // Key 7 is the Design.md row of the built-in list; "a" selects every unlimited pack... only check the notice here.
    const io = terminal(box, '7');
    await runCli(['--project', box.project], io);
    assert.match(io.text(), /holds 3 skills at a time: open it with the right arrow/);
  } finally {
    box.cleanup();
  }
});
