import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const skill = join(root, 'sigmafinanceman');
const read = (p) => readFileSync(join(skill, p), 'utf8');
const masters = read('references/masters.md');
const strategy = read('references/strategy.md');

const PEOPLE = [
  'Elon Musk', 'Warren Buffett', 'Jensen Huang', 'Bill Ackman', 'Charlie Munger', 'Steve Jobs', 'Sam Altman',
  'Jeff Bezos', 'Mark Zuckerberg', 'Stanley Druckenmiller', 'Ben Horowitz', 'Doug Leone', 'Peter Thiel', 'Marc Andreessen',
];

function sections() {
  return masters.split(/^## /m).slice(1).map((s) => ({ name: s.split('\n')[0].trim(), body: s }));
}

test('masters.md holds the 14 people, 10 sourced verbatim quotes each, and their principles', () => {
  const secs = sections();
  assert.deepEqual(secs.map((s) => s.name), PEOPLE);
  for (const s of secs) {
    const quotes = s.body.split('\n').filter((l) => /^\d+\. "/.test(l));
    assert.equal(quotes.length, 10, `${s.name}: 10 quotes`);
    for (const l of quotes) {
      const m = l.match(/^\d+\. "(.+)" - (.+) \| (https?:\/\/\S+)$/);
      assert.ok(m, `${s.name}: a quote needs text, a source and a URL: ${l.slice(0, 70)}`);
      assert.ok(m[1].split(/\s+/).length <= 40, `${s.name}: quote over 40 words: ${l.slice(0, 70)}`);
      assert.ok(m[2].trim().length > 8, `${s.name}: source too thin: ${l.slice(0, 70)}`);
    }
    const tag = s.name.split(' ').pop();
    const principles = s.body.split('\n').filter((l) => l.startsWith(`- ${tag} P`));
    assert.ok(principles.length >= 5 && principles.length <= 6, `${s.name}: 5-6 principles, got ${principles.length}`);
  }
});

test('every principle tag that strategy.md names exists in masters.md', () => {
  const known = new Set([...masters.matchAll(/^- (\w+ P\d+)\./gm)].map((m) => m[1]));
  const used = [...strategy.matchAll(/\b([A-Z][a-z]+) P(\d+)\b/g)].map((m) => `${m[1]} P${m[2]}`);
  assert.ok(used.length > 20, 'strategy.md cites principles');
  for (const t of used) assert.ok(known.has(t), `strategy.md cites ${t}, masters.md has no such principle`);
});

test('SKILL.md links both files and the grill and the final response apply them', () => {
  const md = read('SKILL.md');
  assert.match(md, /\]\(references\/masters\.md\)/);
  assert.match(md, /\]\(references\/strategy\.md\)/);
  assert.match(md, /--principles/);
  assert.match(read('references/grill.md'), /strategy\.md/);
});

function findPython() {
  for (const cmd of ['python3', 'python', 'py']) {
    const r = spawnSync(cmd, ['-c', 'import openpyxl, pptx, sys; print(sys.version_info >= (3, 10))'], { encoding: 'utf8' });
    if (r.status === 0 && r.stdout.trim() === 'True') return cmd;
  }
  return null;
}

test('--principles names the applied principles in every output and rejects an unknown tag', (t) => {
  const python = findPython();
  if (!python) {
    t.skip('python 3.10+ with openpyxl and python-pptx not found');
    return;
  }
  const helper = join(skill, 'scripts', 'finman.py');
  const sample = join(skill, 'assets', 'household-example.json');
  const out = mkdtempSync(join(tmpdir(), 'finman-principles-'));
  const env = { ...process.env, PYTHONDONTWRITEBYTECODE: '1' };
  const bad = spawnSync(python, [helper, 'budget', sample, '--principles', 'Nobody P9', '--out', out], { encoding: 'utf8', env });
  assert.notEqual(bad.status, 0);
  assert.match(bad.stdout + bad.stderr, /Nobody P9/);
  const ok = spawnSync(python, [helper, 'budget', sample, '--principles', 'Buffett P6,Munger P5', '--out', out], { encoding: 'utf8', env });
  assert.equal(ok.status, 0, ok.stdout + ok.stderr);
  const files = readdirSync(out);
  const pick = (ext) => join(out, files.find((f) => f.endsWith(ext)));
  assert.match(readFileSync(pick('.html'), 'utf8'), /Principles applied[^<]*Buffett P6, Munger P5/);
  assert.match(readFileSync(pick('.report.json'), 'utf8'), /Buffett P6, Munger P5/);
  const wb = spawnSync(python, ['-c',
    'import sys, openpyxl; wb = openpyxl.load_workbook(sys.argv[1]); print("Method" in wb.sheetnames and "Buffett P6, Munger P5" in str([c.value for r in wb["Method"].iter_rows() for c in r]))',
    pick('.xlsx')], { encoding: 'utf8' });
  assert.equal(wb.stdout.trim(), 'True');
  const deck = spawnSync(python, ['-c',
    'import sys; from pptx import Presentation; print("Buffett P6, Munger P5" in " ".join(sh.text_frame.text for s in Presentation(sys.argv[1]).slides for sh in s.shapes if sh.has_text_frame))',
    pick('.pptx')], { encoding: 'utf8' });
  assert.equal(deck.stdout.trim(), 'True');
});
