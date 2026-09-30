import { execFileSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { codedError, execNpm } from './release-util.js';

export function parseNpmPackJson(output) {
  const text = String(output);
  const start = text.search(/[\[{]/);
  if (start < 0) {
    throw codedError('npm pack --json produced no JSON', 'pack-failed');
  }
  return JSON.parse(text.slice(start));
}

export function defaultPack(rootDir) {
  const dest = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-release-pack-'));
  const output = execNpm(['pack', '--json', `--pack-destination=${dest}`], {
    cwd: rootDir,
    encoding: 'utf8',
  });
  const parsed = parseNpmPackJson(output);
  const info = Array.isArray(parsed) ? parsed[0] : parsed;
  const tarballPath = path.join(dest, info.filename);
  const bytes = fs.readFileSync(tarballPath);
  const digest = crypto.createHash('sha256').update(bytes).digest('hex');
  // A bare file name: GNU tar reads `C:` in a Windows path as a remote host.
  const contents = execFileSync('tar', ['-tf', info.filename], { cwd: dest, encoding: 'utf8' })
    .split(/\r?\n/)
    .map((line) => line.trim().replace(/\\/g, '/'))
    .filter(Boolean);
  return {
    filename: info.filename,
    digest,
    integrity: info.integrity,
    contents,
    path: tarballPath,
  };
}
