'use strict';

/**
 * sync.js — deterministic registry synchronization command.
 *
 *   node src/registry/sync.js [--fetch] [--dry-run] [--allow-review]
 *
 * Reads upstream `agents.ts` (the pinned revision recorded in
 * `registry/source.json`), verifies its content hash against the recorded
 * pin, parses only declarative fields, normalizes into the canonical
 * attributed snapshot, validates, and emits a normalized semantic diff
 * against the existing snapshot. Unless --dry-run, writes the snapshot only
 * when there are no review-classified changes, or when --allow-review is
 * passed. `--fetch` downloads the pinned revision from the upstream
 * repository and saves it as the local pinned fixture before syncing.
 *
 * The default pin is the real immutable upstream commit recorded in
 * `registry/source.json`; a pseudo-pin is rejected so a release can never
 * masquerade as synchronized from upstream.
 */

import crypto from 'node:crypto';
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
const FIXTURE_PATH = path.join(ROOT, 'test', 'fixtures', 'vercel-skills', 'src', 'agents.ts');
const PIN_PATH = path.join(REGISTRY_DIR, 'source.json');
const SNAPSHOT_PATH = path.join(REGISTRY_DIR, 'agent-hosts.json');

const REVISION_PATTERN = /^[0-9a-f]{40}$/;
const SHA256_PATTERN = /^[0-9a-f]{64}$/;

function sha256(text) {
  return crypto.createHash('sha256').update(text, 'utf8').digest('hex');
}

function parseArgs(argv) {
  const args = { fetch: false, dryRun: false, allowReview: false, source: null };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--dry-run') args.dryRun = true;
    else if (arg === '--allow-review') args.allowReview = true;
    else if (arg === '--fetch') args.fetch = true;
    else if (arg === '--source' && i + 1 < argv.length) args.source = argv[++i];
  }
  return args;
}

function readJson(file) {
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n', 'utf8');
}

/**
 * Load the pinned source record and reject pseudo-pins.
 * @returns {object} pin { repository, pinnedRevision, upstreamFile, contentSha256 }
 */
export function loadPin(pinPath = PIN_PATH) {
  const pin = readJson(pinPath);
  if (!pin || !pin.pinnedRevision || !REVISION_PATTERN.test(pin.pinnedRevision)) {
    throw new Error(
      `registry/source.json must pin an immutable 40-hex upstream revision; got ${JSON.stringify(pin && pin.pinnedRevision)}`
    );
  }
  if (typeof pin.repository !== 'string' || pin.repository.length === 0) {
    throw new Error('registry/source.json must record the upstream repository URL');
  }
  if (!pin.upstreamFile || !pin.contentSha256 || !SHA256_PATTERN.test(pin.contentSha256)) {
    throw new Error('registry/source.json must record the upstream file path and contentSha256');
  }
  return pin;
}

/**
 * Fetch the pinned upstream file from the repository at the pinned revision
 * and save it as the local pinned fixture. Verifies the content hash.
 * @param {object} pin loaded pin record
 * @param {string} [fixturePath] where to save the fetched content
 */
export async function fetchPinnedSource(pin, fixturePath = FIXTURE_PATH) {
  const url = `https://raw.githubusercontent.com/${pin.repository}/${pin.pinnedRevision}/${pin.upstreamFile}`;
  let res;
  try {
    res = await fetch(url);
  } catch (err) {
    throw new Error(`failed to fetch ${url}: ${err.message}`);
  }
  if (!res.ok) {
    throw new Error(`failed to fetch ${url}: HTTP ${res.status}`);
  }
  const text = await res.text();
  const digest = sha256(text);
  if (digest !== pin.contentSha256) {
    throw new Error(
      `fetched content hash ${digest} does not match pinned contentSha256 ${pin.contentSha256} for ${pin.pinnedRevision}`
    );
  }
  fs.mkdirSync(path.dirname(fixturePath), { recursive: true });
  fs.writeFileSync(fixturePath, text, 'utf8');
  return text;
}

/**
 * Synchronize the registry from the pinned upstream source.
 *
 * @param {object} args { fetch, dryRun, allowReview, source? }
 * @param {object} [options] { pin?, previous?, fixturePath? }
 * @returns {object} { ok, snapshot, validation, diff, shouldWrite, errors? }
 */
export function syncRegistry(args, options = {}) {
  const pin = options.pin ?? loadPin();
  const fixturePath = options.fixturePath ?? FIXTURE_PATH;
  const sourcePath = args.source ?? fixturePath;

  let sourceText;
  if (args.fetch) {
    sourceText = fetchPinnedSourceSync(pin, fixturePath);
  } else {
    sourceText = fs.readFileSync(sourcePath, 'utf8');
    const digest = sha256(sourceText);
    if (digest !== pin.contentSha256) {
      return {
        ok: false,
        errors: [
          `source content hash ${digest} does not match pinned contentSha256 ${pin.contentSha256}` +
            ` (source ${sourcePath}); re-fetch with --fetch or update registry/source.json`,
        ],
      };
    }
  }

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

  const previous = options.previous ?? readJson(SNAPSHOT_PATH);
  const diff = previous ? diffSnapshots(previous, snapshot) : null;
  const reviewCount = diff ? diff.summary.review : 0;

  const shouldWrite = !args.dryRun && (args.allowReview || reviewCount === 0);

  if (shouldWrite) {
    writeJson(SNAPSHOT_PATH, snapshot);
    writeJson(PIN_PATH, pin);
  }

  return {
    ok: true,
    snapshot,
    validation,
    diff,
    shouldWrite,
  };
}

// Small sync wrapper so syncRegistry stays pure for tests.
function fetchPinnedSourceSync(pin, fixturePath) {
  const url = `https://raw.githubusercontent.com/${pin.repository}/${pin.pinnedRevision}/${pin.upstreamFile}`;
  throw new Error(`sync --fetch requires async fetch; use runSync() instead (${url})`);
}

/**
 * Async entrypoint used by the CLI. Fetches when requested, then syncs.
 * @param {object} args CLI args
 * @returns {Promise<object>} result of syncRegistry
 */
export async function runSync(args, options = {}) {
  const pin = options.pin ?? loadPin();
  if (args.fetch) {
    await fetchPinnedSource(pin, options.fixturePath ?? FIXTURE_PATH);
  }
  return syncRegistry({ ...args, fetch: false }, options);
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  runSync(args).then((result) => {
    if (!result.ok) {
      for (const err of result.errors) console.error('validation error:', err);
      process.exit(1);
    }
    console.log(`sync: parsed ${result.snapshot.hosts.length} hosts from pinned revision ${loadPin().pinnedRevision}`);
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
  }).catch((err) => {
    console.error('error:', err.message);
    process.exit(1);
  });
}

if (process.argv[1] && path.basename(process.argv[1]) === 'sync.js') {
  main();
}
