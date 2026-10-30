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

// sigmataste writes one plan file at the root, ranked with a verify step per change, and changes nothing else.
const TASTE_PLAN = /^sigmataste-plan-\d{2}-\d{2}-\d{4}\.md$/;
const TASTE_SECTIONS = ['Direction', 'Ranked changes', 'Findings by lens', 'Keep', 'Not judged', 'Next step'];

function sigmataste({ files, result }) {
  const problems = [];
  for (const [name, text] of Object.entries(files)) {
    if (TASTE_PLAN.test(name)) continue;
    const original = path.join(FIXTURE, ...name.split('/'));
    if (!fs.existsSync(original) || fs.readFileSync(original, 'utf8') !== text) problems.push(`changed the target repository: ${name}`);
  }
  const plans = Object.keys(files).filter((name) => TASTE_PLAN.test(name));
  if (plans.length !== 1) return [...problems, `expected one sigmataste-plan-DD-MM-YYYY.md at the root, found ${plans.length}`];
  const [name] = plans;
  const plan = files[name];
  problems.push(...requireInOrder(plan, TASTE_SECTIONS, name));
  problems.push(...requireText(plan, [/^\|\s*#\s*\|\s*Change\s*\|.*\|\s*Verify\s*\|/m, /^\|\s*1\s*\|/m], name));
  const next = plan.split(/^## Next step/m)[1] ?? '';
  if (!/\/(?:sigmaloop|sigmaship|implement-spec)\b/.test(next)) problems.push(`${name}: "Next step" names none of /sigmaloop, /sigmaship, /implement-spec`);
  if (!result.includes(name)) problems.push('reply does not name the plan file');
  return problems;
}

// sigmahuman rewrites docs/ANNOUNCE.md in place: every fact kept, the strong tells gone, nothing else changed.
const HUMAN_FILE = 'docs/ANNOUNCE.md';
const HUMAN_TELLS = /not just|not only|here's the thing|let that sink in|in conclusion|testament|pivotal|thrilled|i hope this helps|let me know|seamless|great news|\u{1F680}|[–—]|\*\*/iu;

function humanFacts(text) {
  return (text.match(/\d+(?:\.\d+)?/g) || []).sort().join(' ');
}

function sigmahuman({ files, result }) {
  const problems = [];
  for (const [name, text] of Object.entries(files)) {
    if (name === HUMAN_FILE) continue;
    const original = path.join(FIXTURE, ...name.split('/'));
    if (!fs.existsSync(original) || fs.readFileSync(original, 'utf8') !== text) problems.push(`changed another file: ${name}`);
  }
  const text = files[HUMAN_FILE];
  if (!text) return [...problems, `missing ${HUMAN_FILE}`];
  const before = fs.readFileSync(path.join(FIXTURE, 'docs', 'ANNOUNCE.md'), 'utf8');
  if (text === before) problems.push(`${HUMAN_FILE}: unchanged`);
  const tell = text.match(HUMAN_TELLS);
  if (tell) problems.push(`${HUMAN_FILE}: AI tell left: ${JSON.stringify(tell[0])}`);
  if (humanFacts(text) !== humanFacts(before)) problems.push(`${HUMAN_FILE}: numbers changed: before [${humanFacts(before)}], after [${humanFacts(text)}]`);
  problems.push(...requireText(text, [/`scores\.json`/, /`saveBest`/, /`src\/scores\.js`/, /`npm test`/], `${HUMAN_FILE} (code spans must survive)`));
  if (!/ANNOUNCE\.md/.test(result)) problems.push('reply does not name the file');
  return problems;
}

// sigmafork copies the repository to out/copy, leaves the original as it was, and writes the course into the copy.
function sigmafork({ files, result }) {
  const problems = [];
  for (const [name, text] of Object.entries(files)) {
    if (name.startsWith('copy/')) continue;
    const original = path.join(FIXTURE, ...name.split('/'));
    if (!fs.existsSync(original) || fs.readFileSync(original, 'utf8') !== text) problems.push(`wrote into the original: ${name}`);
  }
  for (const name of ['copy/package.json', 'copy/src/logic.js']) {
    if (!(name in files)) problems.push(`the copy is missing ${name}`);
  }
  const grill = files['copy/.sigmafork/grill.md'] ?? '';
  if (!grill) problems.push('missing copy/.sigmafork/grill.md');
  else if ((grill.match(/^(?:Q[1-8]|Ruling)\b/gm) || []).length < 8) problems.push('grill.md: expected an answer or Ruling line for each of the 8 questions');
  const guide = files['copy/ONBOARDING.html'] ?? '';
  if (!guide) return [...problems, 'missing copy/ONBOARDING.html'];
  if (/\bFILL\b/.test(guide)) problems.push('ONBOARDING.html: FILL markers left from the template');
  problems.push(...requireText(guide, [/<svg[\s>]/, /Part 2/, /<title>[^<]+<\/title>/], 'ONBOARDING.html'));
  if (!/ONBOARDING\.html/.test(result)) problems.push('reply does not name the guide');
  if (!/isolated/i.test(result)) problems.push('reply does not give the isolation result');
  if (!/anything else/i.test(result)) problems.push('reply does not ask whether anything else is needed');
  return problems;
}

// sigmadesign writes a design system under design/ (DESIGN.md, built CSS, a sample page) and changes no other file.
function sigmadesign({ files, result }) {
  const problems = [];
  for (const [name, text] of Object.entries(files)) {
    if (name.startsWith('design/')) continue;
    const original = path.join(FIXTURE, ...name.split('/'));
    if (!fs.existsSync(original) || fs.readFileSync(original, 'utf8') !== text) problems.push(`changed a file outside design/: ${name}`);
  }
  const design = files['design/DESIGN.md'] ?? '';
  if (!design) return [...problems, 'missing design/DESIGN.md'];
  problems.push(...requireText(design, [/^---\r?\n[\s\S]*?^colors:/m, /^\s+primary:\s*"?#[0-9a-fA-F]{6}/m, /^\s+light-canvas:/m, /^typography:/m, /^rounded:/m, /^components:/m, /^## Overview/m], 'design/DESIGN.md'));
  if (/\bFILL\b/.test(design)) problems.push('design/DESIGN.md: FILL markers left from the template');
  const tokens = files['design/site/tokens.css'] ?? '';
  if (!tokens) problems.push('missing design/site/tokens.css');
  else problems.push(...requireText(tokens, [/:root\s*\{/, /:root\[data-theme="light"\]/, /--primary:\s*#[0-9a-fA-F]{6}/], 'design/site/tokens.css'));
  const components = files['design/site/components.css'] ?? '';
  if (!components) problems.push('missing design/site/components.css');
  else if (/#[0-9a-fA-F]{3,6}\b/.test(components.replace(/\/\*[\s\S]*?\*\//g, ''))) problems.push('design/site/components.css: a colour literal instead of a token');
  const page = files['design/site/index.html'] ?? '';
  if (!page) problems.push('missing design/site/index.html');
  else problems.push(...requireText(page, [/tokens\.css/, /components\.css/, /<title>[^<]+<\/title>/], 'design/site/index.html'));
  if (!/design\/DESIGN\.md/.test(result)) problems.push('reply does not name design/DESIGN.md');
  if (!/contrast/i.test(result)) problems.push('reply does not give the contrast check result');
  if (!/looked|screenshot/i.test(result)) problems.push('reply does not say the page was looked at');
  return problems;
}

// sigmatour reads the repository and writes one tour page under tour/, with the scan's data block and a trace.
function sigmatour({ files, result }) {
  const problems = [];
  for (const [name, text] of Object.entries(files)) {
    if (name.startsWith('tour/')) continue;
    const original = path.join(FIXTURE, ...name.split('/'));
    if (!fs.existsSync(original) || fs.readFileSync(original, 'utf8') !== text) problems.push(`changed a file outside tour/: ${name}`);
  }
  const pageName = Object.keys(files).find((name) => /^tour\/[^/]+-tour\.html$/.test(name));
  if (!pageName) return [...problems, 'missing tour/<name>-tour.html'];
  const page = files[pageName];
  if (/\bFILL\b/.test(page)) problems.push(`${pageName}: FILL markers left from the template`);
  problems.push(...requireText(page, [/id="sigmatour-data">\{/, /<svg[\s>]/, /<title>[^<]+<\/title>/, /What the README says/], pageName));
  if ((page.match(/<li[^>]*class="[^"]*\bstep\b/g) || []).length < 4) problems.push(`${pageName}: the trace has fewer than 4 steps`);
  if (!result.includes(pageName.split('/').pop())) problems.push('reply does not name the tour page');
  if (!/anything else/i.test(result)) problems.push('reply does not ask whether there is anything else to see');
  return problems;
}

// sigmafinanceman writes its files under finance/ (workbook, report data, page) and changes no other file.
function sigmafinanceman({ files, result }) {
  const problems = [];
  for (const [name, text] of Object.entries(files)) {
    if (name.startsWith('finance/')) continue;
    const original = path.join(FIXTURE, ...name.split('/'));
    if (!fs.existsSync(original) || fs.readFileSync(original, 'utf8') !== text) problems.push(`changed a file outside finance/: ${name}`);
  }
  if (!Object.keys(files).some((name) => /^finance\/[^/]+\.xlsx$/.test(name))) problems.push('missing finance/<stem>.xlsx');
  const reportName = Object.keys(files).find((name) => /^finance\/[^/]+\.report\.json$/.test(name));
  if (!reportName) problems.push('missing finance/<stem>.report.json');
  else {
    try {
      const report = JSON.parse(files[reportName]);
      if (!report.hero || !report.hero.value) problems.push(`${reportName}: no hero number`);
      if (!Array.isArray(report.sources) || report.sources.length === 0) problems.push(`${reportName}: no sources`);
    } catch {
      problems.push(`${reportName}: not JSON`);
    }
  }
  const pageName = Object.keys(files).find((name) => /^finance\/[^/]+\.html$/.test(name));
  if (!pageName) problems.push('missing finance/<stem>.html');
  else {
    const page = files[pageName];
    const hero = page.indexOf('class="hero"');
    const table = page.indexOf('<table');
    if (hero === -1 || (table !== -1 && table < hero)) problems.push(`${pageName}: the page does not lead with the answer`);
  }
  if (!/(^|\D)0 errors/.test(result)) problems.push('reply does not give the workbook audit result');
  if (!/Ruling:/.test(result)) problems.push('reply does not list the defaults it took');
  return problems;
}

// sigmaspeedloop scaffolds one project under Projects/<name>/ (signed spec, run file, queue, results header, weights),
// rents nothing in an offline run, and changes no other file.
function sigmaspeedloop({ files, result }) {
  const problems = [];
  for (const [name, text] of Object.entries(files)) {
    if (name.startsWith('Projects/')) continue;
    const original = path.join(FIXTURE, ...name.split('/'));
    if (!fs.existsSync(original) || fs.readFileSync(original, 'utf8') !== text) problems.push(`changed a file outside Projects/: ${name}`);
  }
  const goalName = Object.keys(files).find((name) => /^Projects\/[^/]+\/GOAL\.md$/.test(name));
  if (!goalName) return [...problems, 'missing Projects/<name>/GOAL.md'];
  const dir = goalName.slice(0, -'GOAL.md'.length);
  const goal = files[goalName];
  if (!/Stop line:/.test(goal)) problems.push(`${goalName}: no stop line`);
  const left = goal.match(/<[A-Za-z][^<>:\n]{0,80}>/g); // any template placeholder; links (<https:...>) have a colon
  if (left) problems.push(`${goalName}: template placeholders left: ${[...new Set(left)].join(', ')}`);
  const spec = files[`${dir}SPEC_DRAFT.md`];
  if (!spec) problems.push(`missing ${dir}SPEC_DRAFT.md`);
  else problems.push(...requireText(spec, [/faster/i, /quality/i, /Ruling:/], `${dir}SPEC_DRAFT.md`));
  const ideas = files[`${dir}ideas.tsv`];
  if (!ideas) problems.push(`missing ${dir}ideas.tsv`);
  else {
    const [head, ...rows] = ideas.trim().split(/\r?\n/);
    if (!head.startsWith('id\tstatus\tidea')) problems.push(`${dir}ideas.tsv: the header is not the template header`);
    const pending = rows.filter((row) => row.split('\t')[1] === 'pending');
    if (pending.length < 3) problems.push(`${dir}ideas.tsv: fewer than 3 pending ideas`);
    if (pending.some((row) => !/p=\d{1,3}%\s*$/.test(row))) problems.push(`${dir}ideas.tsv: a pending idea has no p=NN% at the end`);
  }
  const results = files[`${dir}results.tsv`];
  if (!results || !/\tverdict\t/.test(results.split(/\r?\n/)[0])) problems.push(`${dir}results.tsv: missing or no verdict column`);
  const projectName = `${dir}project.json`;
  if (!files[projectName]) problems.push(`missing ${projectName}`);
  else {
    try {
      const weights = JSON.parse(files[projectName]).weights || {};
      const sum = Object.values(weights).reduce((a, b) => a + b, 0);
      if (Math.abs(sum - 1) > 0.011) problems.push(`${projectName}: score weights add up to ${sum}, not 1`);
    } catch {
      problems.push(`${projectName}: not JSON`);
    }
  }
  if (!/Ruling:/.test(result)) problems.push('reply does not list the defaults it took');
  if (!/no (box|instance) (was )?rented|rented nothing|nothing (was )?rented/i.test(result)) problems.push('reply does not say that nothing was rented');
  return problems;
}

// sigmasetup writes only setup files in the repo, keeps the git guard's two parts together,
// and reports every change with its undo.
function sigmasetup({ files, result }) {
  const problems = [];
  const setupFile = (name) => /^(\.claude\/|docs\/agents\/)/.test(name) || name === 'AGENTS.md' || name === 'CLAUDE.md';
  for (const [name, text] of Object.entries(files)) {
    if (setupFile(name)) continue;
    const original = path.join(FIXTURE, ...name.split('/'));
    if (!fs.existsSync(original) || fs.readFileSync(original, 'utf8') !== text) problems.push(`changed a file that is not setup: ${name}`);
  }
  const settings = files['.claude/settings.json'];
  if (settings?.includes('sigma-git-guard.mjs') && !files['.claude/hooks/sigma-git-guard.mjs']) {
    problems.push('.claude/settings.json runs the git guard but .claude/hooks/sigma-git-guard.mjs is missing');
  }
  problems.push(...requireText(result, [/\|\s*Pack\s*\|/i, /\|\s*Undo\s*\|/i], 'reply'));
  return problems;
}

// sigmacourse sets up a course repo (steering, spec with a base rate, a done list, a queue,
// a run file, one check command) and ends with one fenced goal prompt that runs that check.
const COURSE_FILES = ['AGENTS.md', 'docs/course/spec.md', 'docs/course/done.md', 'loop/queue.tsv', 'loop/run.md', 'checks/check.py'];

function sigmacourse({ files, result }) {
  const problems = COURSE_FILES.filter((name) => !files[name]).map((name) => `missing ${name}`);
  const spec = files['docs/course/spec.md'] ?? '';
  if (!/BASE RATE[^\n]*\b(source|assum)/i.test(spec)) problems.push('docs/course/spec.md: the base rate needs a source or a stated assumption');
  const done = files['docs/course/done.md'] ?? '';
  if ((done.match(/^\s*-?\s*R-\d{3}\b/gm) || []).length < 3) problems.push('docs/course/done.md: fewer than 3 numbered requirements');
  if (!/\bDONE\b/.test(done)) problems.push('docs/course/done.md: no completion ladder line (DONE)');
  const rows = (files['loop/queue.tsv'] ?? '').split(/\r?\n/).filter(Boolean);
  if (!/\tdone_when\b/.test(rows[0] ?? '') || rows.length < 2) problems.push('loop/queue.tsv: needs a done_when column and at least one row');
  const prompt = [...result.matchAll(/^```text\r?\n([\s\S]*?)^```/gm)].map((m) => m[1]).find((b) => /checks\/check\.py/.test(b));
  if (!prompt) problems.push('reply has no fenced ```text goal prompt that runs checks/check.py');
  else problems.push(...requireText(prompt, [/loop\/run\.md/, /re-read|every turn/i], 'prompt'));
  return problems;
}

export const CONTRACTS = { 'sigmacreatearena': sigmacreatearena, sigmaloop, sigmataste, sigmahuman, sigmafork, sigmadesign, sigmatour, sigmafinanceman, sigmaspeedloop, sigmasetup, sigmacourse, sigmawritegui, sigmareview, sigmaimprove, sigmabrief, sigmaship, sigmawrite, sigmarefactor, sigmaresearch, sigmadeeplook, sigmafreedom };

export function checkContract(skill, output) {
  const check = CONTRACTS[skill];
  if (!check) throw new Error(`no contract check for ${skill}`);
  return check({ files: {}, result: '', ...output });
}
