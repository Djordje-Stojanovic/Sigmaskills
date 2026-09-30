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

export function execNpm(args, options = {}) {
  if (process.platform !== 'win32') return execFileSync('npm', args, options);
  // Run npm's own entry point with Node, so no shell joins the arguments (DEP0190).
  const npmCli = path.join(path.dirname(process.execPath), 'node_modules', 'npm', 'bin', 'npm-cli.js');
  if (fs.existsSync(npmCli)) return execFileSync(process.execPath, [npmCli, ...args], options);
  return execFileSync('npm.cmd', args, { ...options, shell: true });
}
