// Output-contract checks for the skill evals (issue #43).
// Each check takes { files, result } and returns a list of problems; an empty list is a pass.
// files maps repository-relative paths ('/' separators) to text; result is the agent's final chat reply.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const FIXTURE = path.resolve(import.meta.dirname, '..', 'test', 'fixtures', 'eval-repo');

function headings(text) {
  return [...text.matchAll(/^## (.+?)\s*$/gm)].map((m) => m[1]);
}

function requireInOrder(text, wanted, where) {
  const found = headings(text);
  const problems = [];
  let at = -1;
  for (const name of wanted) {
    const i = found.indexOf(name, at + 1);
    if (i === -1) problems.push(`${where}: missing or out-of-order section "## ${name}"`);
    else at = i;
  }
  return problems;
}

function requireText(text, patterns, where) {
  return patterns.filter((p) => !p.test(text)).map((p) => `${where}: missing ${p}`);
}

// Split a Markdown file into "### " blocks keyed by their heading line.
function blocks(text, headingPattern) {
  const parts = text.split(/^(?=### )/m).filter((part) => headingPattern.test(part.split('\n')[0]));
  return parts;
}

function sigmareview({ files }) {
  const names = Object.keys(files).filter((f) => /^SIGMAREVIEW-\d{4}-\d{2}-\d{2}\.md$/.test(f));
  if (names.length !== 1) return [`expected one SIGMAREVIEW-YYYY-MM-DD.md at the root, found ${names.length}`];
  const name = names[0];
  const text = files[name];
  const problems = [
    ...requireText(text, [/^# SigmaReview — .+/m], name),
    ...requireInOrder(
      text,
      ['Verdict', 'System and promises', 'Fix plan', 'Findings index', 'Findings', 'Coverage'],
      name,
    ),
    ...requireText(
      text,
      [
        /\|\s*Condition\s*\|/,
        /\|\s*Release posture\s*\|/,
        /\|\s*Confirmed findings\s*\|/,
        /\|\s*Highest-leverage fix\s*\|/,
        /\|\s*Wave\s*\|\s*Findings\s*\|\s*Action\s*\|\s*Depends on\s*\|\s*Done when\s*\|/,
        /\|\s*ID\s*\|\s*Priority\s*\|\s*Evidence\s*\|/,
      ],
      name,
    ),
  ];
  const findings = blocks(text, /^### SIG-\d{3} — /);
  if (findings.length === 0) problems.push(`${name}: no "### SIG-### — " findings`);
  findings.forEach((block, i) => {
    const id = block.match(/SIG-\d{3}/)[0];
    const expected = `SIG-${String(i + 1).padStart(3, '0')}`;
    if (id !== expected) problems.push(`${name}: finding ${i + 1} is ${id}, expected ${expected}`);
    if (!new RegExp(`\\|\\s*${id}\\s*\\|`).test(text)) problems.push(`${name}: ${id} missing from the findings index`);
    problems.push(
      ...requireText(
        block,
        [
          /\|\s*Priority\s*\|\s*P[0-3]\b/,
          /\|\s*Evidence\s*\|\s*M[12]\b/,
          /\*\*Broken promise:\*\*/,
          /\*\*What happens:\*\*/,
          /\*\*Impact:\*\*/,
          /\*\*Fix:\*\*/,
          /\*\*Proof test:\*\*/,
          /\*\*Done when:\*\*/,
        ],
        id,
      ),
    );
  });
  return problems;
}

function sigmaimprove({ files }) {
  // Category files are named <category ID>-<slug>.md; other files there, such as an index, are not checked.
  const names = Object.keys(files).filter((f) => /^\.scratch\/sigmaimprove\/[A-I]\d{1,2}-[^/]+\.md$/.test(f));
  if (names.length < 1 || names.length > 20) return [`expected 1–20 category files in .scratch/sigmaimprove/, found ${names.length}`];
  const problems = [];
  const groups = new Set();
  let entries = 0;
  for (const name of names) {
    const text = files[name];
    const title = text.match(/^# SigmaImprove · ([A-I])\d{1,2}\b.*$/m);
    if (!title) problems.push(`${name}: first heading must be "# SigmaImprove · <category ID> <name>"`);
    else groups.add(title[1]);
    problems.push(
      ...requireInOrder(text, ['Where we stand', 'Entries', 'History'], name),
      ...requireText(text, [/\|\s*ID\s*\|\s*Type\s*\|\s*Title\s*\|\s*Impact\s*\|\s*Effort\s*\|\s*Status\s*\|/], name),
    );
    const found = blocks(text, /^### IMP-[A-I]\d{1,2}-\d{2} — .+\((Idea|Signal)\)/);
    if (found.length === 0) problems.push(`${name}: no "### IMP-<cat>-NN — <name> (Idea|Signal)" entries`);
    entries += found.length;
    for (const block of found) {
      const id = block.match(/IMP-[A-I]\d{1,2}-\d{2}/)[0];
      const shape = /\(Idea\)/.test(block.split('\n')[0])
        ? [/\*\*Problem:\*\*/, /\*\*Recommendation:\*\*/, /\*\*Done when:\*\*/]
        : [/\*\*What we see:\*\*/, /\*\*Gap:\*\*/, /\*\*Questions to answer:\*\*/];
      problems.push(...requireText(block, shape, id));
    }
  }
  if (entries < 10) problems.push(`expected at least 10 entries in total, found ${entries}`);
  if (groups.size < 5) problems.push(`expected entries in at least 5 category groups, found ${groups.size}`);
  return problems;
}

function sigmaship({ files }) {
  const body = files['PR-BODY.md'];
  const cleanup = files['CLEANUP.md'];
  if (!body) return ['missing PR-BODY.md (the drafted PR ledger)'];
  const problems = [
    ...requireText(body, [/^Closes #\d+/m, /Spec:.*Map:/], 'PR-BODY.md'),
    ...requireInOrder(body, ['Acceptance', 'Rulings', 'Follow-ups (not in this PR)', 'Review rounds'], 'PR-BODY.md'),
    ...requireText(body, [/^- \[x\] .+/m, /\|\s*Round\s*\|\s*Status\s*\|/], 'PR-BODY.md'),
  ];
  if (/^- \[ \]/m.test(body)) problems.push('PR-BODY.md: an acceptance criterion is still unticked');
  if (!/^\|\s*\d+\s*\|/m.test(body)) problems.push('PR-BODY.md: no review round recorded in the Review rounds table');
  if (!cleanup) problems.push('missing CLEANUP.md (the cleanup verification output)');
  else problems.push(...requireText(cleanup, [/main in sync/, /tree clean/], 'CLEANUP.md'));
  return problems;
}

function sigmabrief({ files, result }) {
  const problems = [];
  if (Object.keys(files).some((f) => /(^|\/)SIGMABRIEF-[^/]*\.md$/.test(f))) problems.push('created a SIGMABRIEF-*.md file');
  // A brief factory leaves the target repository as it found it.
  for (const [name, text] of Object.entries(files)) {
    const original = path.join(FIXTURE, ...name.split('/'));
    if (!fs.existsSync(original) || fs.readFileSync(original, 'utf8') !== text) problems.push(`changed the target repository: ${name}`);
  }
  const dispatch = result.match(/^`?wave \d+ \| .+ \| isolation: (on|off|ask) \| type: (greenfield|finish-PR|skip|blocked|session)`?\s*$/gm) || [];
  if (dispatch.length === 0) problems.push('reply has no dispatch line "wave N | … | isolation: … | type: …"');
  const briefs = [...result.matchAll(/^```text\r?\n([\s\S]*?)^```/gm)].map((m) => m[1]).filter((b) => !/^wave \d+ \|/m.test(b));
  if (briefs.length === 0) problems.push('reply has no fenced ```text brief');
  briefs.forEach((brief, i) => {
    problems.push(...requireText(brief, [/do not merge/i, /DONE \| DONE_WITH_CONCERNS \| BLOCKED/], `brief ${i + 1}`));
  });
  return problems;
}

const JARGON = /\b(orchestration|idempotently|hydrates?|ephemeral|synergistically|operationalize|leveraging|paradigm|facilitates|performant)\b/gi;

function sigmawrite({ files }) {
  const text = files['docs/NOTES.md'];
  if (!text) return ['missing docs/NOTES.md'];
  const problems = requireText(text, [/`step`/, /`saveBest`/, /`src\/scores\.js`/], 'docs/NOTES.md (code names must survive)');
  const jargon = text.match(JARGON);
  if (jargon) problems.push(`docs/NOTES.md: jargon left: ${[...new Set(jargon.map((w) => w.toLowerCase()))].join(', ')}`);
  const prose = text.replace(/^#.*$/gm, '').replace(/`[^`]*`/g, 'x');
  // A sentence ends at . ! or ?, at a blank line, or where a list item starts.
  const sentences = prose.split(/[.!?](?:\s|$)|\n\s*\n|\n\s*(?:[-*+]|\d+\.)\s/).map((s) => s.trim().split(/\s+/).filter(Boolean).length).filter((n) => n > 0);
  const longest = Math.max(0, ...sentences);
  if (longest > 30) problems.push(`docs/NOTES.md: a sentence has ${longest} words (limit 30)`);
  return problems;
}

function sigmarefactor({ files }) {
  const text = files['REFACTOR-SCAN.md'];
  if (!text) return ['missing REFACTOR-SCAN.md'];
  const problems = requireText(
    text,
    [/laloc|fallback/i, /src\/logic\.js[^\n]*\d/, /src\/game\.js[^\n]*\d/, /risk/i, /verif/i],
    'REFACTOR-SCAN.md',
  );
  return problems;
}

function sigmawritegui({ files, result }) {
  const board = files['status-board.html'];
  if (!board) return ['missing status-board.html'];
  const problems = [];
  const template = fs.readFileSync(new URL('../sigmawritegui/template.html', import.meta.url), 'utf8');
  const dataBlock = /\/\* ===== DATA:[\s\S]*?\/\* ===== END DATA ===== \*\//;
  const normalize = (text) => text.replaceAll('\r\n', '\n').replace(dataBlock, 'DATA');
  if (!dataBlock.test(board)) problems.push('status-board.html: missing DATA block');
  if (normalize(board) !== normalize(template)) problems.push('status-board.html: template changed outside DATA');
  const data = board.match(dataBlock)?.[0] ?? '';
  for (const name of ['PAGE', 'DO', 'ANS', 'FYI']) {
    if (!new RegExp('const ' + name + '\\s*=').test(data)) problems.push('status-board.html: missing ' + name);
  }
  try {
    new vm.Script(data);
  } catch {
    problems.push('status-board.html: invalid JavaScript data');
  }
  if (!result.includes('status-board.html')) problems.push('reply: missing board link');
  return problems;
}

function sigmacreatearena({ files, result }) {
  const problems = [];
  const raw = files['arena/arena.json'];
  if (!raw) return ['missing arena/arena.json'];
  let cfg;
  try {
    cfg = JSON.parse(raw);
  } catch {
    return ['arena/arena.json: invalid JSON'];
  }
  if (!cfg.title || !cfg.question) problems.push('arena.json: needs title and question');
  if (!Array.isArray(cfg.metrics) || cfg.metrics.length < 1) problems.push('arena.json: needs at least one metric');
  const groups = Object.keys(cfg.groups || {});
  const players = Object.keys(cfg.players || {});
  if (!groups.length) problems.push('arena.json: needs at least one group');
  if (players.length < 4) problems.push('arena.json: needs at least four players');
  const items = cfg.items || [];
  if (!items.length) problems.push('arena.json: no items');
  for (const item of items) {
    if (!players.includes(item.player) || !groups.includes(item.group)) problems.push('arena.json: item ' + item.id + ' names an unknown player or group');
  }
  if (files['arena/picks.jsonl']) problems.push('arena/picks.jsonl must not exist before the user ranks');
  if (!/http:\/\/127\.0\.0\.1:34\d\d/.test(result)) problems.push('reply: missing the local arena link (port 3410-3499)');
  return problems;
}

function sigmaresearch({ result }) {
  const problems = requireInOrder(result, ['Sources', 'Contradictions', 'Access gaps'], 'reply');
  const sources = result.split(/^## Sources\s*$/m)[1]?.split(/^## /m)[0]?.trim() || '';
  const gaps = result.match(/^## Access gaps\s*\n([\s\S]*)/m)?.[1]?.trim() || '';
  if (!gaps) problems.push('reply: access gaps must be explicit, or None');
  if (/^None\.?$/i.test(sources)) {
    if (!gaps || /^None\.?$/i.test(gaps)) problems.push('reply: no sources requires an access gap');
    return problems;
  }
  const rows = sources.split('\n').filter((line) => /^\|/.test(line.trim()))
    .map((line) => line.trim().slice(1, -1).split(/(?<!\\)\|/).map((cell) => cell.trim()));
  const columns = ['Platform', 'URL', 'Published', 'Accessed', 'Route', 'Scope', 'Evidence'];
  if (rows[0]?.join('|') !== columns.join('|') || rows.length < 3) {
    problems.push('reply: Sources needs the documented source table and at least one source');
    return problems;
  }
  for (const row of rows.slice(2)) {
    if (row.length !== columns.length || row.some((cell) => !cell)) {
      problems.push('reply: every source needs all provenance fields');
      continue;
    }
    if (!/^https?:\/\/\S+$/.test(row[1])) problems.push('reply: source URL must be a web link');
    if (!/^(\d{4}-\d{2}-\d{2}|unknown)$/i.test(row[2])) problems.push('reply: publication date must be dated or unknown');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(row[3])) problems.push('reply: access date is required');
  }
  return problems;
}

function sigmadeeplook({ result }) {
  const problems = requireInOrder(result, ['Evidence', 'Limits'], 'reply');
  const evidence = result.match(/^## Evidence\s*\n([\s\S]*?)(?=^## |(?![\s\S]))/m)?.[1]?.trim() || '';
  const limits = result.match(/^## Limits\s*\n([\s\S]*?)(?=^## |(?![\s\S]))/m)?.[1]?.trim() || '';
  if (!evidence) problems.push('reply: Evidence must list the claims with their sources');
  if (!limits) problems.push('reply: Limits must be explicit, or None');
  const lines = evidence.split('\n').filter((line) => /^\s*(?:[-*]|\d+\.)\s/.test(line));
  if (evidence && !lines.length) problems.push('reply: Evidence needs one bullet per claim');
  for (const line of lines) {
    if (!/`[^`\s]+\.(?:md|json|csv|tsv|txt|srt|jpg|jpeg|png|html|py)\b[^`]*`/.test(line)) problems.push(`reply: evidence line names no artifact path: ${line.trim().slice(0, 60)}`);
    if (!/\b(?:\d{1,2}:\d{2}|page \d+|p\.? ?\d+|cell [A-Z]+\d+|cell \d+|sheet \S+|row \d+|offset \S+|tile \d+|line \d+|facts?|flags?|field)\b/i.test(line)) problems.push(`reply: evidence line names no time, page, cell or offset: ${line.trim().slice(0, 60)}`);
  }
  if (!/view\.html/.test(result)) problems.push('reply: end with the path to view.html');
  if (/-?\d{1,3}\.\d{4,}\s*,\s*-?\d{1,3}\.\d{4,}/.test(result)) problems.push('reply: private coordinates must stay out of the reply');
  return problems;
}

// sigmafreedom changes the target repo's docs; its eval only requires a non-empty final report.
function sigmafreedom({ result }) {
  return result && result.trim() ? [] : ['empty final reply'];
}

// sigmaloop writes one loop file and one prompt; it starts nothing and leaves the target repository as it found it.
const LOOP_FILE = '.scratch/loops/overnight.md';
const LOOP_SECTIONS = ['Stance', 'Goal', 'Crew', 'Each wake', 'Priority', 'Landing', 'Finish'];

function sigmaloop({ files, result }) {
  const problems = [];
  for (const [name, text] of Object.entries(files)) {
    if (name.startsWith('.scratch/loops/')) continue;
    const original = path.join(FIXTURE, ...name.split('/'));
    if (!fs.existsSync(original) || fs.readFileSync(original, 'utf8') !== text) problems.push(`changed the target repository: ${name}`);
  }
  const loop = files[LOOP_FILE];
  if (!loop) return [...problems, `missing ${LOOP_FILE} (the loop file)`];
  for (const name of LOOP_SECTIONS) {
    if (!new RegExp(`^## ${name}\\b`, 'm').test(loop)) problems.push(`${LOOP_FILE}: missing section "## ${name}"`);
  }
  if (!/Stop line:[^\n]*\d{1,2}:\d{2}/.test(loop)) problems.push(`${LOOP_FILE}: the stop line needs a clock time`);
  const prompt = [...result.matchAll(/^```text\r?\n([\s\S]*?)^```/gm)].map((m) => m[1]).find((b) => /^\/loop\b/m.test(b));
  if (!prompt) return [...problems, 'reply has no fenced ```text prompt that starts with /loop'];
  problems.push(...requireText(prompt, [/overnight\.md/, /ScheduleWakeup/, /\d{1,2}:\d{2}/, /re-read/i, /stop: true/], 'prompt'));
  return problems;
}

export const CONTRACTS = { 'sigmacreatearena': sigmacreatearena, sigmaloop, sigmawritegui, sigmareview, sigmaimprove, sigmabrief, sigmaship, sigmawrite, sigmarefactor, sigmaresearch, sigmadeeplook, sigmafreedom };

export function checkContract(skill, output) {
  const check = CONTRACTS[skill];
  if (!check) throw new Error(`no contract check for ${skill}`);
  return check({ files: {}, result: '', ...output });
}
