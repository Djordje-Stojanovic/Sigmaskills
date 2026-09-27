import { randomUUID } from 'node:crypto';
import fs from 'node:fs';

export const LOCK_GRACE_MS = 5000;
export const LOCK_MAX_AGE_MS = 24 * 60 * 60 * 1000;

function alive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try { process.kill(pid, 0); return true; }
  catch (err) { return err.code === 'EPERM'; }
}

// Every create, takeover, and release uses this short exclusive guard. A rename
// alone is insufficient: a second observer could rename the first winner's lock.
function guard(lockPath, action) {
  const dir = `${lockPath}.guard`;
  try { fs.mkdirSync(dir); }
  catch (err) {
    if (err.code !== 'EEXIST') throw err;
    const busy = new Error(`Concurrent SigmaSkills operation in progress at ${dir}. Retry shortly. If a crash left this guard, stop all SigmaSkills processes before removing it.`);
    busy.code = 'lock-busy';
    throw busy;
  }
  try { return action(); }
  finally { fs.rmdirSync(dir); }
}

export function acquireFileLock(lockPath, hooks = {}) {
  const token = randomUUID();
  guard(lockPath, () => {
    let stat;
    try { stat = fs.statSync(lockPath); }
    catch (err) { if (err.code !== 'ENOENT') throw err; }
    if (stat) {
      let existing;
      try { existing = JSON.parse(fs.readFileSync(lockPath, 'utf8')); }
      catch { /* An incomplete record gets a grace period, never immediate deletion. */ }
      const created = Date.parse(existing?.createdAt);
      const age = Date.now() - (Number.isFinite(created) ? created : stat.mtimeMs);
      const incomplete = !Number.isInteger(existing?.pid) || existing.pid <= 0;
      if ((incomplete && age < LOCK_GRACE_MS) || (!incomplete && alive(existing.pid) && age < LOCK_MAX_AGE_MS)) {
        throw new Error(`Concurrent SigmaSkills operation in progress (PID ${existing?.pid || 'unknown'}) at ${lockPath}. Locks expire after 24 hours. To clear one manually, stop all SigmaSkills processes first, then remove this lock.`);
      }
      hooks.beforeTakeover?.();
      const retired = `${lockPath}.stale.${token}`;
      fs.renameSync(lockPath, retired);
      fs.unlinkSync(retired);
    }
    const fd = fs.openSync(lockPath, 'wx');
    try { fs.writeFileSync(fd, JSON.stringify({ pid: process.pid, token, createdAt: new Date().toISOString() })); }
    finally { fs.closeSync(fd); }
  });
  let released = false;
  return () => {
    if (released) return;
    for (let attempt = 0; ; attempt += 1) {
      try {
        guard(lockPath, () => {
          let existing;
          try { existing = JSON.parse(fs.readFileSync(lockPath, 'utf8')); }
          catch (err) { if (err.code === 'ENOENT') return; throw err; }
          if (existing.token === token) fs.unlinkSync(lockPath);
        });
        released = true;
        return;
      } catch (err) {
        if (err.code === 'ENOENT') { released = true; return; }
        if (err.code !== 'lock-busy' || attempt >= 100) throw err;
        // Other processes can finish their short guard while this synchronous caller waits.
        Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 10);
      }
    }
  };
}
