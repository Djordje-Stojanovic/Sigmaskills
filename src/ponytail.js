import fs from 'node:fs';
import path from 'node:path';

// Ponytail (github.com/DietrichGebert/ponytail) turned on for one project, never machine-wide.
// Claude Code, Codex and Pi each read a project file; T3 Code threads read the same files.
export const PONYTAIL_TAG = 'v5.3.3';
const REPO = 'DietrichGebert/ponytail';
const PLUGIN = 'ponytail@ponytail';
const PI_PACKAGE = `git:github.com/${REPO}@${PONYTAIL_TAG}`;
const PI_PREFIX = `git:github.com/${REPO}`;
const GITIGNORE_LINE = '.pi/git/';
const ENV = {
  // Only agents that write code get the rule; read-only search agents skip the 3.5 KB.
  PONYTAIL_SUBAGENT_MATCHER: '^(general-purpose|claude|plan)$',
  PONYTAIL_HIDE_STATUS: '1',
  PONYTAIL_QUIET_STARTUP: '1',
};
const CODEX_BEGIN = '# sigmaskills ponytail begin';
const CODEX_END = '# sigmaskills ponytail end';
const CODEX_BLOCK = `${CODEX_BEGIN}
[marketplaces.ponytail]
source_type = "git"
source = "https://github.com/${REPO}.git"
ref = "${PONYTAIL_TAG}"

[plugins."${PLUGIN}"]
enabled = true
${CODEX_END}
`;

const files = (root) => ({
  claude: path.join(root, '.claude', 'settings.json'),
  codex: path.join(root, '.codex', 'config.toml'),
  pi: path.join(root, '.pi', 'settings.json'),
  gitignore: path.join(root, '.gitignore'),
});

function readText(file) {
  try {
    return fs.readFileSync(file, 'utf8').replace(/^﻿/, '');
  } catch {
    return null;
  }
}

function readJson(file) {
  const text = readText(file);
  return text === null || text.trim() === '' ? {} : JSON.parse(text);
}

function write(file, text) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, text);
}

// An object that ends up empty is deleted, so off leaves a file the way on found it.
function writeJsonOrDelete(file, data) {
  if (Object.keys(data).length === 0) fs.rmSync(file, { force: true });
  else write(file, `${JSON.stringify(data, null, 2)}\n`);
}

function stripCodexBlock(text, file) {
  const start = text.indexOf(CODEX_BEGIN);
  const end = text.indexOf(CODEX_END);
  if (start === -1 && end === -1) return text;
  if (start === -1 || end === -1 || end < start) {
    throw new Error(`${file} has only one of the "${CODEX_BEGIN}" / "${CODEX_END}" lines; fix the block by hand, then run again`);
  }
  return (text.slice(0, start) + text.slice(end + CODEX_END.length).replace(/^\r?\n/, '')).replace(/\n+$/, '\n');
}

export function ponytailOn(root) {
  const f = files(root);

  const claude = readJson(f.claude);
  claude.extraKnownMarketplaces = {
    ...claude.extraKnownMarketplaces,
    ponytail: { source: { source: 'github', repo: REPO, ref: PONYTAIL_TAG } },
  };
  claude.enabledPlugins = { ...claude.enabledPlugins, [PLUGIN]: true };
  claude.env = { ...claude.env, ...ENV };
  write(f.claude, `${JSON.stringify(claude, null, 2)}\n`);

  const codex = readText(f.codex) ?? '';
  const base = stripCodexBlock(codex, f.codex);
  for (const table of [`[plugins."${PLUGIN}"]`, '[marketplaces.ponytail]']) {
    if (base.includes(table)) throw new Error(`${f.codex} already has a ${table} table; remove it, then run again`);
  }
  write(f.codex, base === '' ? CODEX_BLOCK : `${base.replace(/\n*$/, '\n\n')}${CODEX_BLOCK}`);

  const pi = readJson(f.pi);
  pi.packages = [...(pi.packages ?? []).filter((p) => !String(p).startsWith(PI_PREFIX)), PI_PACKAGE];
  write(f.pi, `${JSON.stringify(pi, null, 2)}\n`);

  const ignore = readText(f.gitignore) ?? '';
  if (!ignore.split(/\r?\n/).includes(GITIGNORE_LINE)) {
    write(f.gitignore, `${ignore}${ignore === '' || ignore.endsWith('\n') ? '' : '\n'}${GITIGNORE_LINE}\n`);
  }
}

export function ponytailOff(root) {
  const f = files(root);

  if (fs.existsSync(f.claude)) {
    const claude = readJson(f.claude);
    delete claude.extraKnownMarketplaces?.ponytail;
    delete claude.enabledPlugins?.[PLUGIN];
    for (const key of Object.keys(ENV)) delete claude.env?.[key];
    for (const key of ['extraKnownMarketplaces', 'enabledPlugins', 'env']) {
      if (claude[key] && Object.keys(claude[key]).length === 0) delete claude[key];
    }
    writeJsonOrDelete(f.claude, claude);
  }

  const codex = readText(f.codex);
  if (codex !== null) {
    const rest = stripCodexBlock(codex, f.codex);
    if (rest.trim() === '') fs.rmSync(f.codex, { force: true });
    else write(f.codex, rest);
  }

  if (fs.existsSync(f.pi)) {
    const pi = readJson(f.pi);
    pi.packages = (pi.packages ?? []).filter((p) => !String(p).startsWith(PI_PREFIX));
    if (pi.packages.length === 0) delete pi.packages;
    writeJsonOrDelete(f.pi, pi);
  }

  const ignore = readText(f.gitignore);
  if (ignore !== null) {
    const rest = ignore.split(/\r?\n/).filter((line) => line !== GITIGNORE_LINE).join('\n');
    if (rest.trim() === '') fs.rmSync(f.gitignore, { force: true });
    else write(f.gitignore, rest.endsWith('\n') ? rest : `${rest}\n`);
  }
}

export function ponytailCheck(root) {
  const f = files(root);
  let claude = {};
  let pi = {};
  try { claude = readJson(f.claude); } catch { /* broken JSON counts as off */ }
  try { pi = readJson(f.pi); } catch { /* broken JSON counts as off */ }
  const codex = readText(f.codex) ?? '';
  return {
    claude: claude.enabledPlugins?.[PLUGIN] === true ? 'on' : 'off',
    codex: /\[plugins\."ponytail@ponytail"\]\s*\nenabled = true/.test(codex) ? 'on' : 'off',
    pi: (pi.packages ?? []).some((p) => String(p).startsWith(PI_PREFIX)) ? 'on' : 'off',
  };
}
