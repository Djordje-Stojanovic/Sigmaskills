import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { parseSkillFrontmatter } from '../src/catalog.js';
import { CONTRACTS, checkContract } from '../scripts/eval-contracts.js';

const ROOT = path.resolve(import.meta.dirname, '..');
const SAMPLES = path.join(ROOT, 'test', 'fixtures', 'eval-samples');
const SKILLS = Object.keys(CONTRACTS);

// Read a sample folder as the runner sees a finished run: every file, plus RESULT.txt as the chat reply.
function loadSample(dir) {
  const files = {};
  for (const rel of fs.readdirSync(dir, { recursive: true })) {
    const full = path.join(dir, rel);
    if (fs.statSync(full).isFile()) files[rel.replaceAll('\\', '/')] = fs.readFileSync(full, 'utf8');
  }
  const result = files['RESULT.txt'] ?? '';
  delete files['RESULT.txt'];
  return { files, result };
}

test('evals: every skill folder has a contract check', () => {
  const skills = fs.readdirSync(ROOT).filter((name) => fs.existsSync(path.join(ROOT, name, 'SKILL.md')));
  assert.deepEqual(SKILLS.slice().sort(), skills.sort());
});

for (const skill of SKILLS) {
  test(`evals: ${skill} contract accepts the good sample and rejects the bad one`, () => {
    assert.deepEqual(checkContract(skill, loadSample(path.join(SAMPLES, skill, 'good'))), []);
    assert.notDeepEqual(checkContract(skill, loadSample(path.join(SAMPLES, skill, 'bad'))), []);
  });
}

test('evals: the fixture repository has a game with a seeded wall bug', () => {
  const logic = fs.readFileSync(path.join(ROOT, 'test', 'fixtures', 'eval-repo', 'src', 'logic.js'), 'utf8');
  assert.match(logic, /head\[0\] > WIDTH/);
});

// Deterministic keyword router: a prompt word counts for a skill when its description's
// "Use when" part has it, and against the skill when its "Do not use" part has it.
const STOP = new Set('this that with from what these them their into make have your next every give'.split(' '));
const stem = (word) => word.slice(0, 5);
const words = (text) => new Set((text.toLowerCase().match(/[a-z]{4,}/g) || []).filter((w) => !STOP.has(w)).map(stem));

function route(prompt) {
  const scores = SKILLS.map((skill) => {
    const { description } = parseSkillFrontmatter(fs.readFileSync(path.join(ROOT, skill, 'SKILL.md'), 'utf8'));
    const [use, avoid = ''] = description.split(/Do not use/i);
    const useWords = words(use);
    const avoidWords = words(avoid);
    let score = 0;
    for (const w of words(prompt)) score += (useWords.has(w) ? 1 : 0) - (avoidWords.has(w) ? 1 : 0);
    return { skill, score };
  });
  return scores.sort((a, b) => b.score - a.score);
}

test('evals: near-miss prompts route to the right skill and not its neighbour', () => {
  const cases = JSON.parse(fs.readFileSync(path.join(ROOT, 'test', 'fixtures', 'skill-triggers.json'), 'utf8'));
  assert.deepEqual([...new Set(cases.map((c) => c.skill))].sort(), SKILLS.slice().sort(), 'every skill needs cases');
  for (const { prompt, skill, near } of cases) {
    const [first, second] = route(prompt);
    assert.equal(first.skill, skill, `"${prompt}" routed to ${first.skill}, expected ${skill}`);
    assert.ok(first.score > second.score, `"${prompt}" tied between ${first.skill} and ${second.skill}`);
    assert.ok(route(prompt).find((r) => r.skill === near).score < first.score, `"${prompt}" also fits ${near}`);
  }
});

test('evals: sigmaship contract rejects unticked criteria and an empty review rounds table', () => {
  const sample = loadSample(path.join(SAMPLES, 'sigmaship', 'good'));
  const body = sample.files['PR-BODY.md'];
  const unticked = body.replace(/^- \[x\] (A test covers)/m, '- [ ] $1');
  assert.notDeepEqual(checkContract('sigmaship', { ...sample, files: { ...sample.files, 'PR-BODY.md': unticked } }), []);
  const noRounds = body.replace(/^\| 1 \|.*\n?/m, '');
  assert.notDeepEqual(checkContract('sigmaship', { ...sample, files: { ...sample.files, 'PR-BODY.md': noRounds } }), []);
});

test('evals: sigmabrief contract rejects edits to the target repository', () => {
  const sample = loadSample(path.join(SAMPLES, 'sigmabrief', 'good'));
  const logic = fs.readFileSync(path.join(ROOT, 'test', 'fixtures', 'eval-repo', 'src', 'logic.js'), 'utf8');
  const fixture = { 'src/logic.js': logic };
  assert.deepEqual(checkContract('sigmabrief', { ...sample, files: fixture }), []);
  const edited = { 'src/logic.js': logic.replace('head[0] > WIDTH', 'head[0] >= WIDTH') };
  assert.notDeepEqual(checkContract('sigmabrief', { ...sample, files: edited }), []);
  assert.notDeepEqual(checkContract('sigmabrief', { ...sample, files: { ...fixture, 'PLAN.md': 'plan' } }), []);
});
