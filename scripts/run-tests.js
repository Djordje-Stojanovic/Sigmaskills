import { readdirSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const testDir = join(root, 'test');
const files = readdirSync(testDir)
  .filter((name) => name.endsWith('.test.js'))
  .sort()
  .map((name) => join(testDir, name));

if (files.length === 0) {
  console.error('no test/*.test.js files found');
  process.exit(1);
}

const result = spawnSync(process.execPath, ['--test', ...files], {
  cwd: root,
  stdio: 'inherit',
  env: process.env,
});
process.exit(result.status === null ? 1 : result.status);
