import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const reference = fs.readFileSync(new URL('../sigmarefactor/references/scan.md', import.meta.url), 'utf8');
const recipe = reference.match(/```javascript\r?\n([\s\S]*?)```/)[1];
const rankFiles = vm.runInNewContext(`${recipe}; rankFiles`);

test('native scan counts omitted directories, tied counts, and physical line endings', () => {
  const texts = { 'packages/z.js': 'a\r\nb\r\n', 'bin/a.js': 'a\nb', 'new.js': 'a\nb\nc', 'empty.js': '', 'test/t.js': '\r\n', 'config.js': 'x\r' };
  const result = rankFiles(Object.keys(texts), (file) => texts[file]);
  assert.deepEqual(Array.from(result.top, (file) => [file.path, file.lines]), [
    ['new.js', 3], ['bin/a.js', 2], ['packages/z.js', 2], ['config.js', 1], ['test/t.js', 1],
  ]);
  assert.equal(result.files.find((file) => file.path === 'empty.js').lines, 0);
  assert.equal(result.complete, true);
});

test('fallback needs no laloc and returns fewer than five eligible files without padding', () => {
  const result = rankFiles(['untracked.js', 'untracked.js'], () => 'one line');
  assert.equal(result.top.length, 1);
  assert.equal(result.top[0].lines, 1);
});

test('unreadable eligible files make the ranking incomplete', () => {
  const result = rankFiles(['readable.js', 'blocked.js'], (file) => {
    if (file === 'blocked.js') throw new Error('access denied');
    return 'source';
  });
  assert.equal(result.complete, false);
  assert.equal(result.unreadable[0].path, 'blocked.js');
  assert.equal(result.unreadable[0].error, 'access denied');
});
