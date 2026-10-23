import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const scripts = join(root, 'sigmafinanceman', 'scripts');

function findPython() {
  for (const cmd of ['python3', 'python', 'py']) {
    const r = spawnSync(cmd, ['-c', 'import sys; print(sys.version_info >= (3, 10))'], { encoding: 'utf8' });
    if (r.status === 0 && r.stdout.trim() === 'True') return cmd;
  }
  return null;
}

// FRED hangs for some Linux clients (seen 2026-10-23 on three hosts: every read timed out, so every company model failed).
// The 10-year rate must then come from the Yahoo ^TNX chart, after one short FRED try, not three 40-second ones.
const probe = String.raw`
import io, json, sys, urllib.request
sys.path.insert(0, sys.argv[1])
calls = []
class Resp(io.BytesIO):
    headers = {}
    def __enter__(self): return self
    def __exit__(self, *a): return False
def fake(req, timeout=None):
    url = req.full_url
    calls.append((url, timeout))
    if "fred.stlouisfed.org" in url:
        raise TimeoutError("The read operation timed out")
    if "%5ETNX" in url or "^TNX" in url:
        return Resp(json.dumps({"chart": {"result": [{"meta": {"regularMarketPrice": 4.953, "regularMarketTime": 1792695593}}]}}).encode())
    raise AssertionError("unexpected url " + url)
urllib.request.urlopen = fake
import fin_data
fin_data.time.sleep = lambda s: None
rf, day, src = fin_data.risk_free()
fred = [c for c in calls if "fred" in c[0]]
print(json.dumps({"rf": rf, "day": day, "src": src, "fred_calls": len(fred), "fred_timeout": max(t for _, t in fred)}))
`;

test('sigmafinanceman takes the 10-year rate from Yahoo ^TNX when FRED does not answer', { timeout: 60000 }, (t) => {
  const python = findPython();
  if (!python) {
    t.skip('python 3.10+ not found');
    return;
  }
  const env = { ...process.env, PYTHONDONTWRITEBYTECODE: '1', SIGMAFIN_CACHE: mkdtempSync(join(tmpdir(), 'sigmafin-rf-')) };
  const r = spawnSync(python, ['-c', probe, scripts], { encoding: 'utf8', env });
  assert.equal(r.status, 0, (r.stdout || '') + (r.stderr || ''));
  const out = JSON.parse(r.stdout.trim().split('\n').pop());
  assert.ok(Math.abs(out.rf - 0.04953) < 1e-9, `rf ${out.rf}`);
  assert.match(out.day, /^\d{4}-\d{2}-\d{2}$/);
  assert.match(out.src, /TNX/);
  assert.equal(out.fred_calls, 1, 'FRED is tried once, then the fallback');
  assert.ok(out.fred_timeout <= 15, `FRED timeout ${out.fred_timeout} s`);
});
