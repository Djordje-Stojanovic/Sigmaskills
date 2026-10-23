import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

/** A sandbox: a project folder, a fake home, a folder of local git "remotes", and an env that points at them. */
export function createSandbox() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-packs-'));
  const project = path.join(root, 'project');
  const home = path.join(root, 'home');
  const remotes = path.join(root, 'remotes');
  for (const dir of [project, home, remotes]) fs.mkdirSync(dir, { recursive: true });
  const env = {
    ...process.env,
    HOME: home,
    USERPROFILE: home,
    SIGMA_GIT_BASE: `${remotes.replace(/\\/g, '/')}/`,
    CI: '',
  };
  delete env.NO_COLOR;
  delete env.SIGMA_STATE_DIR;
  delete env.CLAUDE_CONFIG_DIR;
  return {
    root, project, home, remotes, env,
    cleanup: () => fs.rmSync(root, { recursive: true, force: true }),
  };
}

const GIT = ['-c', 'user.email=test@example.com', '-c', 'user.name=Test', '-c', 'commit.gpgsign=false'];

function git(cwd, ...args) {
  return execFileSync('git', [...GIT, ...args], { cwd, stdio: ['ignore', 'pipe', 'pipe'], encoding: 'utf8' }).trim();
}

/**
 * Create a local git repo at <remotes>/<owner>/<name> with skills under `skillsPath`.
 * `skills` maps skill id to the body text of its SKILL.md.
 */
export function createRemote(remotes, repo, skills, skillsPath = 'skills') {
  const dir = path.join(remotes, ...repo.split('/'));
  fs.mkdirSync(dir, { recursive: true });
  git(dir, 'init', '-q');
  git(dir, 'config', 'uploadpack.allowAnySHA1InWant', 'true');
  writeSkills(dir, skills, skillsPath);
  git(dir, 'add', '-A');
  git(dir, 'commit', '-q', '-m', 'init');
  return dir;
}

export function writeSkills(dir, skills, skillsPath = 'skills') {
  for (const [id, body] of Object.entries(skills)) {
    const skillDir = path.join(dir, skillsPath, id);
    fs.mkdirSync(path.join(skillDir, 'references'), { recursive: true });
    fs.writeFileSync(path.join(skillDir, 'SKILL.md'), `---\nname: ${id}\ndescription: ${body}\n---\n\n# ${id}\n`);
    fs.writeFileSync(path.join(skillDir, 'references', 'note.md'), `note for ${id}\n`);
  }
}

export function commitAll(dir, message = 'change') {
  git(dir, 'add', '-A');
  git(dir, 'commit', '-q', '-m', message);
}

/** Write files (relative path to text) into a remote and commit them. Returns the new commit SHA. */
export function commitFiles(dir, files, message = 'files') {
  for (const [rel, text] of Object.entries(files)) {
    const target = path.join(dir, ...rel.split('/'));
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, text);
  }
  commitAll(dir, message);
  return headSha(dir);
}

export function headSha(dir) {
  return git(dir, 'rev-parse', 'HEAD');
}

/** An empty remote at <remotes>/<owner>/<name> that accepts a fetch of any commit. */
export function createEmptyRemote(remotes, repo) {
  const dir = path.join(remotes, ...repo.split('/'));
  fs.mkdirSync(dir, { recursive: true });
  git(dir, 'init', '-q');
  git(dir, 'config', 'uploadpack.allowAnySHA1InWant', 'true');
  return dir;
}

/** Tag the current commit of a remote made by createRemote(). */
export function tagRemote(dir, name) {
  git(dir, 'tag', name);
}

/** Remove a skill folder from a remote and commit, like an upstream that moved a skill. */
export function removeSkillFromRemote(dir, id, skillsPath = 'skills') {
  fs.rmSync(path.join(dir, skillsPath, id), { recursive: true, force: true });
  commitAll(dir, `remove ${id}`);
}

/** Write the owner's config with a git pack called `acme` and a folder pack called `local`. */
export function writeUserConfig(home, config) {
  const dir = path.join(home, '.sigmaskills');
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'packs.json'), JSON.stringify(config, null, 2));
}

export const ACME_PACK = {
  id: 'acme',
  title: 'Acme',
  blurb: 'Test pack.',
  aliases: ['ac'],
  sources: [{ type: 'git', repo: 'acme/skills', path: 'skills', skills: [{ id: 'alpha', description: 'Alpha skill.' }, { id: 'beta', description: 'Beta skill.' }] }],
};

export function createMockIo(env) {
  let stdout = '';
  let stderr = '';
  return {
    env,
    stdout: { write: (text) => { stdout += text; } },
    stderr: { write: (text) => { stderr += text; } },
    getStdout: () => stdout,
    getStderr: () => stderr,
  };
}
