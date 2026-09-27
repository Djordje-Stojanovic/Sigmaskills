#!/usr/bin/env node
// On-demand skill evals (issue #43). Not part of npm test or CI: each run calls a model and costs money.
//
//   node scripts/eval-skills.js [skill...]
//
// For each skill: copy test/fixtures/eval-repo to a temp Git repository with a local bare "origin",
// install the skill in .claude/skills/, run `claude -p` headless, then check the output contract.
// User settings, MCP servers, gh, and web tools are off, and the only remote is a local folder.
// This is a guard, not a sandbox: allowed git and node commands could still reach the network.
import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { CONTRACTS, checkContract } from './eval-contracts.js';

const ROOT = path.resolve(import.meta.dirname, '..');
const FIXTURE = path.join(ROOT, 'test', 'fixtures', 'eval-repo');
const TOTAL_BUDGET_USD = 15;
const RUN_BUDGET_USD = 4;
const OFFLINE = 'This is an offline eval. Do not use gh, GitHub, or the network. The "origin" remote is a local folder. Do not ask questions; use the defaults.';

function prompts(out) {
  const today = new Date().toISOString().slice(0, 10);
  return {
    sigmareview: `/sigmareview Review this repository. ${OFFLINE} Write the report and commit it on branch sigmareview/${today} as the skill says, and push that branch to origin. Skip the pull request. Leave that branch checked out.`,
    sigmaimprove: `/sigmaimprove Improve this product. ${OFFLINE} Use the local-file tracker under .scratch/sigmaimprove/ and compare with the leaders from your own knowledge.`,
    sigmabrief: `/sigmabrief Write briefs for the two local issues docs/issues/1-wall-collision.md and docs/issues/2-pause.md. approval: auto. ${OFFLINE} The issues are local files, not GitHub issues.`,
    sigmaship: `/sigmaship Ship issue #1, described in docs/issues/1-wall-collision.md. ${OFFLINE} There is no pull request or CI: write the PR ledger body to ${out}/PR-BODY.md instead of opening a PR, keep it updated, and treat local \`npm test\` as CI. Do one review round yourself. Then merge the branch into main locally, push main to origin, clean up as land.md says, and write the output of the Verify commands to ${out}/CLEANUP.md.`,
    sigmawrite: `/sigmawrite Rewrite docs/NOTES.md in place so an outsider can follow it. Keep its meaning.`,
    sigmarefactor: `/sigmarefactor Run steps 1 to 3 on this repository. ${OFFLINE} Do not edit any code. Instead of waiting for agreement, write the scan, your reading notes, and the choices you would offer to REFACTOR-SCAN.md at the repository root, then stop.`,
  };
}

function git(cwd, ...args) {
  execFileSync('git', args, { cwd, stdio: 'pipe' });
}

function readTree(dir, skip = new Set(['.git', '.claude', 'node_modules'])) {
  const files = {};
  for (const rel of fs.readdirSync(dir, { recursive: true })) {
    const parts = rel.split(path.sep);
    if (parts.some((p) => skip.has(p))) continue;
    const full = path.join(dir, rel);
    if (fs.statSync(full).isFile()) files[parts.join('/')] = fs.readFileSync(full, 'utf8');
  }
  return files;
}

function runSkill(skill, budget) {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), `sigma-eval-${skill}-`));
  const repo = path.join(work, 'snake-lite');
  const out = path.join(work, 'out');
  fs.cpSync(FIXTURE, repo, { recursive: true });
  fs.mkdirSync(out);
  git(work, 'init', '-q', '--bare', '-b', 'main', 'origin.git');
  git(repo, 'init', '-q', '-b', 'main');
  git(repo, 'config', 'user.name', 'eval');
  git(repo, 'config', 'user.email', 'eval@example.invalid');
  git(repo, 'add', '-A');
  git(repo, 'commit', '-q', '-m', 'Snake Lite fixture');
  git(repo, 'remote', 'add', 'origin', path.join(work, 'origin.git'));
  git(repo, 'push', '-q', '-u', 'origin', 'main');
  fs.cpSync(path.join(ROOT, skill), path.join(repo, '.claude', 'skills', skill), { recursive: true });
  fs.appendFileSync(path.join(repo, '.git', 'info', 'exclude'), '.claude/\n');

  const args = [
    '-p', prompts(out.replaceAll('\\', '/'))[skill],
    '--output-format', 'json',
    '--setting-sources', 'project',
    '--strict-mcp-config',
    '--no-session-persistence',
    '--permission-mode', 'acceptEdits',
    '--add-dir', work,
    '--allowedTools', 'Bash(git *)', 'Bash(node *)', 'Bash(npm test*)', 'Bash(ls *)', 'Bash(wc *)',
    '--disallowedTools', 'Bash(gh *)', 'WebFetch', 'WebSearch',
    '--max-budget-usd', budget.toFixed(2),
  ];
  const started = Date.now();
  const run = spawnSync('claude', args, { cwd: repo, encoding: 'utf8', timeout: 45 * 60_000, maxBuffer: 64 * 1024 * 1024 });
  const seconds = Math.round((Date.now() - started) / 1000);
  fs.writeFileSync(path.join(work, 'claude-output.json'), run.stdout || '');

  let json = {};
  try {
    json = JSON.parse(run.stdout);
  } catch {
    const reason = run.error?.message || run.stderr?.trim().split('\n').pop() || `exit ${run.status}`;
    return { skill, work, seconds, cost: null, tokens: null, problems: [`claude did not return JSON: ${reason}`] };
  }
  const usage = json.usage || {};
  const tokens = ['input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens']
    .reduce((sum, key) => sum + (usage[key] || 0), 0);
  const files = { ...readTree(repo), ...readTree(out) };
  const problems = json.is_error ? [`claude reported an error: ${json.subtype || json.result}`] : [];
  problems.push(...checkContract(skill, { files, result: json.result || '' }));
  return { skill, work, seconds, cost: json.total_cost_usd ?? null, tokens, problems };
}

const skills = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(CONTRACTS);
for (const skill of skills) if (!CONTRACTS[skill]) throw new Error(`unknown skill: ${skill}`);

let spent = 0;
const rows = [];
for (const skill of skills) {
  const left = TOTAL_BUDGET_USD - spent;
  if (left < 0.5) {
    rows.push({ skill, skipped: true });
    continue;
  }
  console.error(`running ${skill} (budget $${Math.min(RUN_BUDGET_USD, left).toFixed(2)}) …`);
  const row = runSkill(skill, Math.min(RUN_BUDGET_USD, left));
  spent += row.cost || 0;
  rows.push(row);
}

console.log('| Skill | Result | Time | Cost (USD) | Tokens | Problems |');
console.log('|---|---|---:|---:|---:|---|');
for (const r of rows) {
  if (r.skipped) {
    console.log(`| ${r.skill} | skipped (budget) | — | — | — | — |`);
    continue;
  }
  const cost = r.cost === null ? 'not available' : r.cost.toFixed(2);
  const tokens = r.tokens === null ? 'not available' : r.tokens.toLocaleString('en-US');
  const result = r.problems.length ? 'fail' : 'pass';
  console.log(`| ${r.skill} | ${result} | ${r.seconds} s | ${cost} | ${tokens} | ${r.problems.join('; ').replaceAll('|', '/') || '—'} |`);
}
console.log(`\nTotal cost: $${spent.toFixed(2)}. Run folders: ${rows.filter((r) => r.work).map((r) => r.work).join(', ')}`);
process.exitCode = rows.some((r) => r.skipped || r.problems.length) ? 1 : 0;
