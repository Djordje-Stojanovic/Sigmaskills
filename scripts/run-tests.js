import { mkdtempSync, readdirSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
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

// Pack once for every test file that needs the tarball (see test/packed.js).
const packDir = mkdtempSync(join(tmpdir(), 'sigma-test-pack-'));
// Slow real-tool checks (LibreOffice, media tools) run only with SIGMA_SLOW_TESTS=1.
const env = { ...process.env, ...(process.env.SIGMA_SLOW_TESTS ? {} : { FINMAN_NO_SOFFICE: '1' }) };
const pack = spawnSync('npm pack --silent --pack-destination "' + packDir + '"', { cwd: root, shell: true, encoding: 'utf8' });
const tarball = pack.status === 0 ? pack.stdout.trim().split(/\r?\n/).pop().trim() : '';
if (tarball && spawnSync('tar', ['-xzf', tarball], { cwd: packDir }).status === 0) {
  env.SIGMA_TEST_TARBALL = join(packDir, tarball);
  env.SIGMA_TEST_PACKAGE = join(packDir, 'package');
}

const result = spawnSync(process.execPath, ['--test', ...files], { cwd: root, stdio: 'inherit', env });
rmSync(packDir, { recursive: true, force: true });
process.exit(result.status === null ? 1 : result.status);
