// One shared `npm pack` for the whole run. scripts/run-tests.js packs once and sets SIGMA_TEST_TARBALL
// and SIGMA_TEST_PACKAGE; run alone, a test file falls back to packing and installing for itself.
import { execSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');

export function packInto(tmpDir) {
  const shared = process.env.SIGMA_TEST_TARBALL;
  if (shared && fs.existsSync(shared)) {
    fs.copyFileSync(shared, path.join(tmpDir, path.basename(shared)));
    return path.basename(shared);
  }
  const out = execSync(`npm pack --pack-destination "${tmpDir}"`, { cwd: ROOT, encoding: 'utf8' }).trim();
  return out.split(/\r?\n/).pop().trim();
}

// Same tree `npm install <tarball>` leaves in node_modules, without starting npm.
export function installTarball(appDir, tarballPath) {
  const unpacked = process.env.SIGMA_TEST_PACKAGE;
  if (!unpacked || !fs.existsSync(unpacked)) {
    execSync('npm init -y', { cwd: appDir, encoding: 'utf8', stdio: 'pipe' });
    execSync(`npm install "${tarballPath}"`, { cwd: appDir, encoding: 'utf8', stdio: 'pipe' });
    return;
  }
  fs.writeFileSync(path.join(appDir, 'package.json'), '{"name":"test-app","version":"1.0.0"}\n');
  fs.cpSync(unpacked, path.join(appDir, 'node_modules', '@djordje-stojanovic', 'sigmaskills'), { recursive: true });
}
