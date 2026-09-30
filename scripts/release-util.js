import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

export function codedError(message, code) {
  const err = new Error(message);
  err.code = code;
  return err;
}

export function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

export function persistJson(file, payload) {
  const tmp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  fs.renameSync(tmp, file);
}

// Escape the dots of a version so it can sit inside a RegExp.
export function versionPattern(version) {
  return String(version).replace(/\./g, '\\.');
}

/**
 * True only when a failed gh, npm, or git lookup says the thing does not exist.
 * A missing binary, a network error, or a 5xx is not "absent".
 */
export function isNotFoundError(err) {
  if (!err || err.code === 'ENOENT') return false;
  const text = `${err.message || ''}\n${err.stderr || ''}\n${err.stdout || ''}`;
  return /\bE404\b|\bHTTP 404\b|\b404 Not Found\b|\b(?:release|tag|run|package|version) not found\b|unknown revision/i.test(text);
}

/** Run a lookup. A 404 gives `absent`; any other error stops the run. */
export function absentOn404(lookup, absent) {
  try {
    return lookup();
  } catch (err) {
    if (isNotFoundError(err)) return absent;
    throw err;
  }
}

/** Create a git tag. A tag that already exists is fine; any other error throws. */
export function createGitTag(tag, commit, { cwd, run = execFileSync } = {}) {
  try {
    run('git', ['tag', tag, commit], { cwd, encoding: 'utf8' });
  } catch (err) {
    if (!/already exists/i.test(`${err?.message || ''}\n${err?.stderr || ''}`)) throw err;
  }
}

export function execNpm(args, options = {}) {
  if (process.platform !== 'win32') return execFileSync('npm', args, options);
  // Run npm's own entry point with Node, so no shell joins the arguments (DEP0190).
  const npmCli = path.join(path.dirname(process.execPath), 'node_modules', 'npm', 'bin', 'npm-cli.js');
  if (fs.existsSync(npmCli)) return execFileSync(process.execPath, [npmCli, ...args], options);
  return execFileSync('npm.cmd', args, { ...options, shell: true });
}
