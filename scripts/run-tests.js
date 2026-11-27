import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { availableParallelism, tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

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
const started = Date.now();
const BUDGET = 180; // owner limit for the default run, packing included; slow sets go behind SIGMA_SLOW_TESTS=1
const fast = !process.env.SIGMA_SLOW_TESTS;
const left = () => (fast ? { timeout: Math.max(1000, BUDGET * 1000 - (Date.now() - started)) } : {});
// No __pycache__: a Python test writing one races the tests that hash the same skill tree.
const env = { ...process.env, PYTHONDONTWRITEBYTECODE: '1', ...(process.env.SIGMA_SLOW_TESTS ? {} : { FINMAN_NO_SOFFICE: '1' }) };
const pack = spawnSync('npm pack --silent --pack-destination "' + packDir + '"', { cwd: root, shell: true, encoding: 'utf8', ...left() });
const tarball = pack.status === 0 ? pack.stdout.trim().split(/\r?\n/).pop().trim() : '';
if (tarball && spawnSync('tar', ['-xzf', tarball], { cwd: packDir }).status === 0) {
  env.SIGMA_TEST_TARBALL = join(packDir, tarball);
  env.SIGMA_TEST_PACKAGE = join(packDir, 'package');
}

env.SIGMA_TEST_TIMING = join(packDir, 'timing.json');
// Most tests wait on child processes, so run more files at once than there are cores.
const concurrency = String(Math.max(8, availableParallelism() * 2));
// Hard limits in the default run: a test that awaits past 60 s fails; a blocking one, like a hang, ends at the run's kill.
// shortcut: on Windows the kill reaches only the runner, not test files it started; add a tree kill if one ever lingers.
const result = spawnSync(process.execPath, ['--test', '--test-concurrency', concurrency, ...(fast ? ['--test-timeout', '60000'] : []),
  '--test-reporter', 'spec', '--test-reporter-destination', 'stdout',
  '--test-reporter', pathToFileURL(join(root, 'scripts', 'test-timing.js')).href, '--test-reporter-destination', join(packDir, 'timing.log'),
  ...files], { cwd: root, stdio: 'inherit', env, ...left() });
const timing = existsSync(env.SIGMA_TEST_TIMING) ? JSON.parse(readFileSync(env.SIGMA_TEST_TIMING, 'utf8')) : {};
const seconds = (Date.now() - started) / 1000;
console.log(`npm test took ${seconds.toFixed(0)} s (budget ${BUDGET} s)`);
if (fast && seconds > BUDGET) {
  const slowest = Object.entries(timing).sort((a, b) => b[1] - a[1]).slice(0, 5);
  for (const [file, secs] of slowest) console.error(`  ${secs.toFixed(0).padStart(4)} s  ${file.slice(root.length + 1)}`);
  if (!slowest.length) console.error('  the run was killed before the timing report was written; time one file with node --test <file>');
  console.error(`FAIL: npm test took ${seconds.toFixed(0)} s, over the ${BUDGET} s budget; move the slow test behind SIGMA_SLOW_TESTS=1 with a fast fixture test in its place`);
  rmSync(packDir, { recursive: true, force: true });
  process.exit(124);
}
rmSync(packDir, { recursive: true, force: true });
process.exit(result.status === null ? 1 : result.status);
