import assert from 'node:assert/strict';
import { execFileSync, execSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

const ROOT = path.resolve(import.meta.dirname, '..');

test('tarball: pack, inspect contents, install into sandbox, and spawn installed executable', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-tarball-test-'));
  try {
    // 1. Pack tarball into tmpDir
    const packOutput = execSync(`npm pack --pack-destination "${tmpDir}"`, {
      cwd: ROOT,
      encoding: 'utf8',
    }).trim();

    const tarballFileName = packOutput.split(/\r?\n/).pop()?.trim();
    assert.ok(tarballFileName, 'expected tarball filename from npm pack');
    const tarballPath = path.join(tmpDir, tarballFileName);
    assert.ok(fs.existsSync(tarballPath), `tarball does not exist at ${tarballPath}`);

    // 2. List tarball contents using tar -tf
    const listOutput = execFileSync('tar', ['-tf', tarballPath], {
      encoding: 'utf8',
    });
    const packedFiles = listOutput
      .split(/\r?\n/)
      .map((f) => f.trim().replace(/\\/g, '/'))
      .filter(Boolean);

    // 3. Verify required files are included
    const requiredFiles = [
      'package/package.json',
      'package/README.md',
      'package/LICENSE',
      'package/CHANGELOG.md',
      'package/manifest.json',
      'package/bin/sigmaskills.js',
      'package/src/catalog.js',
      'package/src/cli.js',
      'package/src/customization.js',
      'package/src/plan.js',
      'package/src/prepack.js',
      'package/src/project-lock.js',
      'package/src/revision.js',
      'package/src/state.js',
      'package/src/transaction.js',
      'package/sigmareview/SKILL.md',
      'package/sigmareview/agents/openai.yaml',
      'package/sigmareview/references/report-contract.md',
      'package/sigmareview/references/review-method.md',
      'package/sigmaperformance/SKILL.md',
      'package/sigmaperformance/agents/openai.yaml',
      'package/sigmabrief/SKILL.md',
      'package/sigmabrief/agents/openai.yaml',
      'package/sigmawrite/SKILL.md',
      'package/sigmawrite/agents/openai.yaml',
    ];

    for (const req of requiredFiles) {
      assert.ok(
        packedFiles.includes(req),
        `tarball is missing required file: ${req}`,
      );
    }

    // 4. Verify excluded files / paths are strictly absent
    const forbiddenPrefixes = [
      'package/test/',
      'package/docs/',
      'package/.github/',
      'package/.agents/',
      'package/.cursor/',
      'package/.git/',
    ];
    const forbiddenExact = [
      'package/skills-lock.json',
      'package/.env',
    ];

    for (const file of packedFiles) {
      for (const prefix of forbiddenPrefixes) {
        assert.ok(
          !file.startsWith(prefix),
          `tarball contains forbidden file from ${prefix}: ${file}`,
        );
      }
      for (const exact of forbiddenExact) {
        assert.notEqual(
          file,
          exact,
          `tarball contains forbidden file: ${file}`,
        );
      }
    }

    // 5. Install the tarball into an isolated test app directory
    const appDir = path.join(tmpDir, 'test-app');
    fs.mkdirSync(appDir, { recursive: true });
    execSync('npm init -y', { cwd: appDir, encoding: 'utf8' });
    execSync(`npm install "${tarballPath}"`, { cwd: appDir, encoding: 'utf8' });

    const installedBin = path.join(appDir, 'node_modules', 'sigmaskills', 'bin', 'sigmaskills.js');
    assert.ok(fs.existsSync(installedBin), `installed bin script missing at ${installedBin}`);

    // Spawn --version
    const versionOut = execFileSync('node', [installedBin, '--version'], {
      cwd: appDir,
      encoding: 'utf8',
    }).trim();
    assert.equal(versionOut, '0.1.0');

    // Spawn --help
    const helpOut = execFileSync('node', [installedBin, '--help'], {
      cwd: appDir,
      encoding: 'utf8',
    });
    assert.match(helpOut, /Usage:\s+sigmaskills/i);
    assert.match(helpOut, /sigmareview/);
    assert.match(helpOut, /sigmaperformance/);
    assert.match(helpOut, /sigmabrief/);
    assert.match(helpOut, /sigmawrite/);

    // Spawn list --json
    const jsonOut = execFileSync('node', [installedBin, 'list', '--json'], {
      cwd: appDir,
      encoding: 'utf8',
    });
    const parsed = JSON.parse(jsonOut);
    assert.equal(parsed.name, 'sigmaskills');
    assert.equal(parsed.version, '0.1.0');
    assert.equal(parsed.skills.length, 4);
    for (const skill of parsed.skills) {
      assert.match(skill.revision, /^[a-f0-9]{64}$/);
    }

    // Spawn install --dry-run --json on isolated project
    const isolatedProject = path.join(tmpDir, 'isolated-proj');
    fs.mkdirSync(isolatedProject, { recursive: true });

    const dryRunJsonOut = execFileSync(
      'node',
      [installedBin, 'install', 'sigmawrite', '--dry-run', '--json', '--project', isolatedProject],
      { cwd: appDir, encoding: 'utf8' },
    );
    const dryRunParsed = JSON.parse(dryRunJsonOut);
    assert.equal(dryRunParsed.skill, 'sigmawrite');
    assert.equal(dryRunParsed.dryRun, true);
    assert.ok(!fs.existsSync(path.join(isolatedProject, '.agents')));

    // Spawn real install on isolated project
    const installOut = execFileSync(
      'node',
      [installedBin, 'install', 'sigmawrite', '--project', isolatedProject],
      { cwd: appDir, encoding: 'utf8' },
    );
    assert.match(installOut, /Installed SigmaWrite \(sigmawrite\)/);
    assert.ok(fs.existsSync(path.join(isolatedProject, '.agents', 'skills', 'sigmawrite', 'SKILL.md')));
    assert.ok(fs.existsSync(path.join(isolatedProject, 'skills-lock.json')));
    assert.ok(fs.existsSync(path.join(isolatedProject, '.agents', 'state.json')));

    // Verify skills-lock.json is timestamp-free and sorted
    const lockRaw = fs.readFileSync(path.join(isolatedProject, 'skills-lock.json'), 'utf8');
    assert.ok(!lockRaw.includes('installedAt'));
    assert.ok(!lockRaw.includes('destination'));
    const lockParsed = JSON.parse(lockRaw);
    assert.equal(lockParsed.release, '0.1.0');
    assert.match(lockParsed.skills.sigmawrite.revision, /^[a-f0-9]{64}$/);

    // Verify state.json records ownedPaths and baseHashes
    const stateRaw = fs.readFileSync(path.join(isolatedProject, '.agents', 'state.json'), 'utf8');
    const stateParsed = JSON.parse(stateRaw);
    assert.equal(stateParsed.scope, 'project');
    assert.equal(stateParsed.skills.sigmawrite.method, 'copy');
    assert.ok(stateParsed.skills.sigmawrite.ownedPaths.length > 0);
    assert.ok(stateParsed.skills.sigmawrite.baseHashes['SKILL.md']);

    // Spawn real install on isolated project with isolated custom state directory
    const customStateDir = path.join(tmpDir, 'custom-state-dir');
    const customStateProject = path.join(tmpDir, 'custom-state-proj');
    fs.mkdirSync(customStateProject, { recursive: true });

    execFileSync(
      'node',
      [installedBin, 'install', 'sigmabrief', '--project', customStateProject, '--state-dir', customStateDir],
      { cwd: appDir, encoding: 'utf8' },
    );
    assert.ok(fs.existsSync(path.join(customStateProject, '.agents', 'skills', 'sigmabrief', 'SKILL.md')));
    assert.ok(fs.existsSync(path.join(customStateProject, 'skills-lock.json')));
    assert.ok(fs.existsSync(path.join(customStateDir, 'state.json')));

    // Spawn install on unowned existing folder to verify fail-closed behavior
    const unownedProject = path.join(tmpDir, 'unowned-proj');
    const unownedSkillDir = path.join(unownedProject, '.agents', 'skills', 'sigmawrite');
    fs.mkdirSync(unownedSkillDir, { recursive: true });
    fs.writeFileSync(path.join(unownedSkillDir, 'SKILL.md'), 'foreign content', 'utf8');

    assert.throws(
      () => {
        execFileSync('node', [installedBin, 'install', 'sigmawrite', '--project', unownedProject], {
          cwd: appDir,
          encoding: 'utf8',
          stdio: 'pipe',
        });
      },
      (err) => {
        const out = (err.stdout || '') + (err.stderr || '');
        return out.includes('already exists and is not owned by SigmaSkills') || err.status !== 0;
      },
      'install should fail closed on unowned directory',
    );
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('tarball: packaging fails when manifest or skill resources are malformed (prepack gate)', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-pack-fail-'));
  try {
    // Copy package files to tmpDir
    fs.cpSync(ROOT, tmpDir, {
      recursive: true,
      filter: (src) => !src.includes('node_modules') && !src.includes('.git'),
    });

    // Introduce a malformed customization marker in a skill
    const skillPath = path.join(tmpDir, 'sigmawrite', 'SKILL.md');
    const validContent = fs.readFileSync(skillPath, 'utf8');
    fs.writeFileSync(skillPath, validContent.replace('<sigmaskills-custom>', '<broken-custom>'), 'utf8');

    // Attempting npm pack in this directory must fail during prepack
    assert.throws(
      () => {
        execSync('npm pack', {
          cwd: tmpDir,
          encoding: 'utf8',
          stdio: 'pipe',
        });
      },
      (err) => {
        const output = (err.stdout || '') + (err.stderr || '');
        return output.includes('Prepack validation failed') || err.status !== 0;
      },
      'npm pack should fail when customization marker is malformed',
    );
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});
