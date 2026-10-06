import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { execFileSync } from 'node:child_process';
import vm from 'node:vm';

const ROOT = path.resolve(import.meta.dirname, '..');

test('easytalk: installs its self-contained board in another project', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-easytalk-'));
  try {
    execFileSync(process.execPath, [path.join(ROOT, 'bin/sigmaskills.js'), 'install', 'easytalk', '--project', project, '--copy', '--yes']);
    for (const file of ['SKILL.md', 'template.html', 'agents/openai.yaml']) {
      assert.equal(fs.readFileSync(path.join(project, '.agents/skills/easytalk', file), 'utf8'), fs.readFileSync(path.join(ROOT, 'easytalk', file), 'utf8'));
    }
  } finally {
    fs.rmSync(project, { recursive: true, force: true });
  }
});

test('easytalk: board scripts compile and example data covers all card types without lab dependencies', () => {
  const html = fs.readFileSync(path.join(ROOT, 'easytalk/template.html'), 'utf8');
  const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
  assert.equal(scripts.length, 2);
  scripts.forEach((script) => new vm.Script(script));
  const data = vm.runInNewContext(`${scripts[0]}; ({ PAGE, DO, ANS, FYI })`);
  assert.ok(data.PAGE.title);
  assert.ok(data.DO.some((card) => card.o && card.o[card.rec]));
  assert.ok(data.DO.some((card) => card.p));
  assert.ok(data.DO.some((card) => card.act));
  assert.ok(data.ANS.some((card) => card.q && card.t));
  assert.ok(data.FYI.some((card) => card.t));
  const ids = [...data.DO, ...data.ANS, ...data.FYI].map((card) => card.id);
  assert.equal(new Set(ids).size, ids.length);
  assert.doesNotMatch(html, /storge|Postiz|YouTube|Design_Experiments|\.claude\/skills|https?:\/\/|src=["']/i);
});
