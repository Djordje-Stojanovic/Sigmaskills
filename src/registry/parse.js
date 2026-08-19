'use strict';

/**
 * parse.js — extract declarative Agent Host data from upstream registry text.
 *
 * Sigma never executes upstream TypeScript, detector, or path-building code.
 * This parser reads upstream `agents.ts` as untrusted text and extracts only
 * literal, declarative fields: host ids, display names, project/global
 * destination formulas, aliases, platform declarations, and env-var
 * detection metadata. Conditional helpers are extracted as declarative
 * case lists (probe + formula), never evaluated.
 */

/** Env-var names referenced in a text fragment (metadata, never evaluated). */
export function extractEnvVars(text) {
  const names = new Set();
  const re = /(?:env|process\.env)\.([A-Z][A-Z0-9_]*)/g;
  let m;
  while ((m = re.exec(text)) !== null) names.add(m[1]);
  return [...names].sort();
}

/** Capture the value of a single-line field like `  skillsDir: '...',`. */
function field(body, name) {
  const re = new RegExp('^\\s*' + name + '\\s*:\\s*([^\\n]+)', 'm');
  const m = re.exec(body);
  if (!m) return null;
  let value = m[1].trim();
  value = value.replace(/,$/, '').trim();
  return value;
}

/** Unquote a single-quoted upstream literal. Returns null when malformed. */
function quoted(value) {
  const m = /^'((?:[^'\\]|\\.)*)'$/.exec(value.trim());
  return m ? m[1] : null;
}

const JOIN_RE = /^join\(([A-Za-z0-9_.]+)((?:,\s*'((?:[^'\\]|\\.)*)')*)\)$/;

/** Parse a destination formula. Forms: join(...) | '<path>' | undefined | <fn>(). */
export function parseDirFormula(value) {
  const raw = value.trim();
  if (!raw) return null;
  if (raw === 'undefined') return { kind: 'none', raw };

  const quotedPath = quoted(raw);
  if (quotedPath !== null) return { kind: 'literal', path: quotedPath, raw };

  const join = JOIN_RE.exec(raw);
  if (join) {
    const segmentsRe = /'((?:[^'\\]|\\.)*)'/g;
    const segments = [];
    let sm;
    while ((sm = segmentsRe.exec(raw)) !== null) segments.push(sm[1]);
    return { kind: 'join', base: join[1], segments, raw };
  }

  const fnRe = /^([A-Za-z0-9_]+)\(\)$/;
  const fn = fnRe.exec(raw);
  if (fn) return { kind: 'function', name: fn[1], raw };

  return { kind: 'unknown', raw };
}

const PROBE_RE = /(?:existsSync|pathExists)\(join\(([A-Za-z0-9_.]+)\s*,\s*'([^']*)'\)\)/g;
const RETURN_RE = /return\s+(join\([^;]*\)|[^;\n]+);/g;

/**
 * Declaratively extract a conditional helper `function <name>(...) { ... }`.
 * Returns { kind: 'conditional', base, cases: [{ probe, formula }] } where
 * cases are (probe, return-join) pairs and the final return is the default.
 * Guards and returns are parsed as text; nothing is evaluated.
 */
export function parseConditionalHelper(sourceText, name) {
  const anchor = 'function ' + name;
  let idx = sourceText.indexOf(anchor);
  if (idx === -1) return null;
  let p = sourceText.indexOf('(', idx + anchor.length);
  if (p === -1) return null;
  let depth = 1;
  let q = p + 1;
  for (; q < sourceText.length; q++) {
    const ch = sourceText[q];
    if (ch === '(') depth++;
    else if (ch === ')') { depth--; if (depth === 0) break; }
  }
  if (depth !== 0) return null;
  let brace = sourceText.indexOf('{', q);
  if (brace === -1) return null;
  const bodyStart = brace + 1;
  let braceDepth = 1;
  let i = bodyStart;
  for (; i < sourceText.length; i++) {
    const ch = sourceText[i];
    if (ch === '{') braceDepth++;
    else if (ch === '}') {
      braceDepth--;
      if (braceDepth === 0) break;
    }
  }
  const body = sourceText.slice(bodyStart, i);

  const probes = [];
  let pm;
  while ((pm = PROBE_RE.exec(body)) !== null) {
    probes.push({ index: pm.index, end: pm.index + pm[0].length, probe: pm[2] });
  }

  const cases = [];
  let rm;
  while ((rm = RETURN_RE.exec(body)) !== null) {
    let probe = null;
    for (const p of probes) {
      if (p.end > rm.index) break;
      const between = body.slice(p.end, rm.index);
      if (!between.includes('}')) probe = p.probe;
    }
    const formula = parseDirFormula(rm[1]);
    cases.push({ probe, formula });
  }
  if (cases.length === 0) return null;
  const first = cases.find((c) => c.formula && c.formula.base);
  const base = first ? first.formula.base : null;
  return { kind: 'conditional', base, cases };
}

/** Boolean value of an upstream literal boolean field. */
function bool(value) {
  if (value === null) return null;
  if (value === 'true') return true;
  if (value === 'false') return false;
  return null;
}

/** Parse one host entry body into a declarative record. */
function parseHostBody(id, body, line, sourceText) {
  const name = quoted(field(body, 'name')) ?? id;
  const displayName = quoted(field(body, 'displayName')) ?? name;
  const project = parseDirFormula(field(body, 'skillsDir'));
  const globalRaw = field(body, 'globalSkillsDir');
  let global = parseDirFormula(globalRaw);
  if (global && global.kind === 'function') {
    const conditional = parseConditionalHelper(sourceText, global.name);
    if (conditional) global = conditional;
  }
  const aliasesRaw = field(body, 'aliases');
  const aliases = aliasesRaw ? aliasesRaw.replace(/^\[|\]$/g, '').split(',').map((s) => s.trim()) : [];
  const platformsRaw = field(body, 'platforms');
  const platforms = platformsRaw ? platformsRaw.replace(/^\[|\]$/g, '').split(',').map((s) => s.trim()) : [];
  const showInUniversalList = bool(field(body, 'showInUniversalList'));
  const showInUniversalPrompt = bool(field(body, 'showInUniversalPrompt'));
  const envVars = extractEnvVars(body);

  return {
    id,
    name,
    displayName,
    project,
    global,
    aliases,
    platforms,
    universal: showInUniversalList !== false,
    universalPrompt: showInUniversalPrompt !== false,
    envVars,
    line,
  };
}

/**
 * Parse upstream agents.ts text into declarative host records.
 */
export function parseAgents(agentsText) {
  const hosts = [];
  const entryRe = /^  '?([A-Za-z0-9_-]+)'?: \{([\s\S]*?)\n  \},$/gm;
  let m;
  while ((m = entryRe.exec(agentsText)) !== null) {
    const id = m[1];
    const body = m[2];
    const line = 1 + agentsText.slice(0, m.index).split('\n').length;
    hosts.push(parseHostBody(id, body, line, agentsText));
  }
  return hosts;
}
