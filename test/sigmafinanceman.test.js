import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const script = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'sigmafinanceman', 'scripts', 'finman.py');
const python = ['python3', 'python'].find((cmd) => spawnSync(cmd, ['-c', 'import openpyxl, pptx']).status === 0);

test('sigmafinanceman: offline selftest of every model, the reverse DCF, the scenarios and the page', { skip: !python && 'python with openpyxl and python-pptx not found' }, () => {
  const r = spawnSync(python, [script, 'selftest'], { encoding: 'utf8', env: { ...process.env, FINMAN_NO_SOFFICE: '1' } });
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(r.stdout, /PASS {2}Reverse DCF: the implied growth gives back the price/);
  assert.match(r.stdout, /PASS {2}Post-money SAFE owns amount \/ cap/);
});

// SKILL.md plus every reference file must stay at or under 50,000 tokens on the OpenAI tokenizer (o200k_base).
// With tiktoken installed the count is exact; without it, bytes / 3 stands in: this prose runs about 3.9 bytes a token,
// so the estimate over-counts and fails before the real cap does, never after.
test('sigmafinanceman: SKILL.md and its references stay within 50,000 o200k_base tokens', (t) => {
  const dir = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'sigmafinanceman');
  const files = ['SKILL.md', ...readdirSync(path.join(dir, 'references')).filter((f) => f.endsWith('.md')).map((f) => path.join('references', f))];
  const count = python && spawnSync(python, ['-c', [
    'import sys, tiktoken',
    'e = tiktoken.get_encoding("o200k_base")',
    'print(sum(len(e.encode(open(f, encoding="utf-8").read())) for f in sys.argv[1:]))',
  ].join('\n'), ...files], { cwd: dir, encoding: 'utf8' });
  if (count && count.status === 0) {
    const tokens = Number(count.stdout.trim());
    t.diagnostic(`${tokens} tokens (tiktoken o200k_base)`);
    assert.ok(tokens <= 50000, `${tokens} tokens, cap 50,000`);
    return;
  }
  const bytes = files.reduce((n, f) => n + statSync(path.join(dir, f)).size, 0);
  t.diagnostic(`tiktoken not installed: estimate ${Math.ceil(bytes / 3)} tokens from ${bytes} bytes (pip install tiktoken for the exact count)`);
  assert.ok(bytes / 3 <= 50000, `${bytes} bytes estimate ${Math.ceil(bytes / 3)} tokens, cap 50,000`);
});
