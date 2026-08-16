'use strict';

/**
 * sync.js — deterministic registry synchronization command.
 *
 *   node src/registry/sync.js [--source <upstream agents.ts path>]
 *                             [--dry-run]
 *                             [--allow-review]
 *
 * Reads upstream `agents.ts`, parses only declarative fields, normalizes into
 * the canonical attributed snapshot, validates, and emits a normalized
 * semantic diff against the existing snapshot. Unless --dry-run, writes the
 * snapshot and source pin only when there are no review-classified changes,
 * or when --allow-review is passed.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseAgents } from './parse.js';
import { normalizeHost, buildSnapshot } from './normalize.js';
import { validateSnapshot } from './validate.js';
import { diffSnapshots } from './diff.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..', '..');
const REGISTRY_DIR = path.join(ROOT, 'registry');

const DEFAULT_SOURCE = path.join(ROOT, 'test', 'fixtures', 'vercel-skills', 'src', 'agents.ts');
const DEFAULT_PIN = {
  repository: 'vercel-labs/skills',
  pinnedRevision: 'pinned-fixture',
  upstreamFile: 'src/agents.ts',
};

function parseArgs(argv) {
  const args = { source: DEFAULT_SOURCE, dryRun: false, allowReview: false };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--dry-run') args.dryRun = true;
    else if (arg === '--allow-review') args.allowReview = true;
    else if (arg === '--source' && i + 1 < argv.length) args.source = argv[++i];
  }
  return args;
}

function readSnapshot() {
  const file = path.join(REGISTRY_DIR, 'agent-hosts.json');
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function readPin() {
  const file = path.join(REGISTRY_DIR, 'source.json');
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n', 'utf8');
}

export function syncRegistry(args, options = {}) {
  const sourcePath = args.source;
  const sourceText = fs.readFileSync(sourcePath, 'utf8');
  const pin = options.pin ?? DEFAULT_PIN;

  const parsed = parseAgents(sourceText);
  const hosts = parsed.map((h) => normalizeHost(h, pin));
  const snapshot = buildSnapshot(hosts, pin);

  const validation = validateSnapshot(snapshot);
  if (!validation.valid) {
    return {
      ok: false,
      errors: [...validation.errors, ...Object.values(validation.hostErrors)],
    };
  }

  const previous = options.previous ?? readSnapshot();
  const diff = previous ? diffSnapshots(previous, snapshot) : null;
  const reviewCount = diff ? diff.summary.review : 0;

  const shouldWrite = !args.dryRun && (args.allowReview || reviewCount === 0);

  if (shouldWrite) {
    writeJson(path.join(REGISTRY_DIR, 'agent-hosts.json'), snapshot);
    writeJson(path.join(REGISTRY_DIR, 'source.json'), pin);
  }

  return {
    ok: true,
    snapshot,
    validation,
    diff,
    shouldWrite,
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const result = syncRegistry(args);
  if (!result.ok) {
    for (const err of result.errors) console.error('validation error:', err);
    process.exit(1);
  }
  console.log(`sync: parsed ${result.snapshot.hosts.length} hosts from ${args.source}`);
  if (result.diff) {
    console.log('diff summary:', JSON.stringify(result.diff.summary));
    for (const change of result.diff.changes) {
      console.log(`  ${change.authority.padEnd(6)} ${change.id} ${change.kind}` +
        (change.fields ? ' [' + change.fields.join(', ') + ']' : ''));
    }
  }
  if (result.shouldWrite) {
    console.log('wrote registry/agent-hosts.json + registry/source.json');
  } else if (args.dryRun) {
    console.log('dry run: no files written');
  } else {
    console.log('review-classified changes present; registry not written (use --allow-review to force)');
  }
}

if (process.argv[1] && path.basename(process.argv[1]) === 'sync.js') {
  main();
}
