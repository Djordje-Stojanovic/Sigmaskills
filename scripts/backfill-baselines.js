// Record skill baselines for Releases tagged before `release --write-identities` kept them.
// Usage: node scripts/backfill-baselines.js v0.1.0 v0.2.0 ...   (safe to run again)
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { appendReleaseBaselines, hashSkillsAtRef } from './baselines.js';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const tags = process.argv.slice(2);
if (tags.length === 0) {
  console.error('usage: node scripts/backfill-baselines.js <tag>...');
  process.exit(1);
}
for (const tag of tags) {
  const skills = hashSkillsAtRef(root, tag);
  appendReleaseBaselines(root, tag.replace(/^v/, ''), skills);
  console.log(`${tag}: ${Object.keys(skills).join(', ')}`);
}
