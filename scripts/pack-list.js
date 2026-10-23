#!/usr/bin/env node
/**
 * Maintainer script: list the skills a transform source produces, to paste into registry/packs.json.
 *
 *   node scripts/pack-list.js <transform> <repo checkout> <source path> [repo name]
 *
 * Example, after cloning anthropics/financial-services at the pinned commit:
 *   node scripts/pack-list.js financial-services ../financial-services plugins anthropics/financial-services
 *
 * It builds the skills into a temporary folder, prints `[{ id, description, group }]` as JSON and
 * removes the folder. A description is cut to its first sentence, at most 150 characters.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildTransform } from '../src/pack-transform.js';

const [kind, repoRoot, sourcePath = '', repo = ''] = process.argv.slice(2);
if (!kind || !repoRoot) {
  console.error('usage: node scripts/pack-list.js <transform> <repo checkout> <source path> [repo name]');
  process.exit(1);
}

function shortDescription(text) {
  const flat = String(text).replace(/\s+/g, ' ').trim();
  const first = flat.split(/(?<=[.!?])\s/)[0];
  return first.length > 150 ? `${first.slice(0, 147).trimEnd()}...` : first;
}

const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigmaskills-list-'));
try {
  const list = buildTransform(kind, { repoRoot: path.resolve(repoRoot), sourcePath, outDir, revision: '', repo, skills: [] });
  const rows = list
    .map((item) => ({ id: item.id, description: shortDescription(item.description), ...(item.group ? { group: item.group } : {}) }))
    .sort((a, b) => a.id.localeCompare(b.id));
  console.log(JSON.stringify(rows, null, 2));
} finally {
  fs.rmSync(outDir, { recursive: true, force: true });
}
