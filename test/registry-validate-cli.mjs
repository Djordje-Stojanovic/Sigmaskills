import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { validateSnapshot } from '../src/registry/validate.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const snapshotPath = path.join(ROOT, 'registry', 'agent-hosts.json');
const schemaPath = path.join(ROOT, 'registry', 'schema.json');

const snapshot = JSON.parse(fs.readFileSync(snapshotPath, 'utf8'));
const schema = JSON.parse(fs.readFileSync(schemaPath, 'utf8'));

// Structural schema checks (schemaVersion, generatedFrom, host shape, contracts).
const structural = validateSnapshot(snapshot);
if (!structural.valid) {
  console.error('structural validation failed:', structural.errors);
  process.exit(1);
}

// Cross-check the committed schema.json declares the same shape we validate.
if (schema.schemaVersion !== undefined && schema.schemaVersion !== 1) {
  console.error('schema.json must target schemaVersion 1');
  process.exit(1);
}
const hostSchema = schema.definitions && schema.definitions.host;
if (!hostSchema || !Array.isArray(hostSchema.required) || !hostSchema.required.includes('universal')) {
  console.error('schema.json must require universal membership on every host');
  process.exit(1);
}

console.log(`registry valid: ${snapshot.hosts.length} hosts match schema contracts`);
