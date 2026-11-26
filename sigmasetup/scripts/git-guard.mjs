#!/usr/bin/env node
// Per-project git guard for Claude Code and Antigravity: blocks commands that destroy work nobody can get back.
// install <dir>: copy this file to <dir>/.claude/hooks/ and <dir>/.agents/hooks/, add one PreToolUse entry to
// <dir>/.claude/settings.json (Claude Code) and one hook to <dir>/.agents/hooks.json (Antigravity).
// remove <dir>: take all of it out again. status <dir>: say whether it is on. No argument: run as the hook (JSON on stdin).
// Branch deletes stay allowed: after a squash merge `git branch -D` is normal cleanup.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HOOK_FILE = 'sigma-git-guard.mjs';
const COMMAND = `node "$CLAUDE_PROJECT_DIR/.claude/hooks/${HOOK_FILE}"`;
const MATCHER = 'Bash|PowerShell';
// Antigravity runs a workspace hook from the folder that holds hooks.json (.agents/, agy 1.5.16) and names its shell tool run_command.
const AGY_NAME = 'sigma-git-guard';
const AGY_ENTRY = { PreToolUse: [{ matcher: 'run_command', hooks: [{ type: 'command', command: `node hooks/${HOOK_FILE}` }] }] };

// Git options that come before the subcommand and take a value in the next word.
const GLOBAL_WITH_VALUE = new Set(['-C', '-c', '--git-dir', '--work-tree', '--namespace', '--exec-path', '--config-env']);

function gitCalls(command) {
  const calls = [];
  // Separators inside quotes (a commit message) do not start a new command.
  const unquoted = command.replace(/"[^"]*"|'[^']*'/g, (q) => q.replace(/[;|&\n]/g, ' '));
  for (const segment of unquoted.split(/&&|\|\||[;|\n]/)) {
    const words = segment.trim().match(/"[^"]*"|'[^']*'|\S+/g) || [];
    const at = words.findIndex((w) => /(^|[\\/])git(\.exe)?$/i.test(w.replace(/^["']|["']$/g, '')));
    if (at < 0) continue;
    let i = at + 1;
    while (i < words.length && words[i].startsWith('-')) i += GLOBAL_WITH_VALUE.has(words[i]) ? 2 : 1;
    if (i < words.length) calls.push({ sub: words[i], args: words.slice(i + 1).map((w) => w.replace(/^["']|["']$/g, '')) });
  }
  return calls;
}

const shortFlag = (args, letter) => args.some((a) => new RegExp(`^-[a-zA-Z]*${letter}[a-zA-Z]*$`).test(a));

export function blockReason(command) {
  for (const { sub, args } of gitCalls(command || '')) {
    if (sub === 'push' && (args.some((a) => /^--force(-with-lease)?(=|$)/.test(a) || a === '--mirror' || /^\+/.test(a)) || shortFlag(args, 'f'))) {
      return 'force push rewrites history on the remote';
    }
    if (sub === 'reset' && args.includes('--hard')) return 'reset --hard throws away uncommitted work';
    if (sub === 'clean' && (args.includes('--force') || shortFlag(args, 'f'))) return 'clean -f deletes untracked files for good';
    const wholeTree = args.includes('.') || args.includes(':/');
    if (sub === 'checkout' && wholeTree) return 'checkout . throws away every uncommitted change';
    const forced = args.includes('--force') || shortFlag(args, 'f');
    if ((sub === 'checkout' || sub === 'switch') && (forced || args.includes('--discard-changes'))) {
      return `${sub} --force throws away every uncommitted change`;
    }
    if (sub === 'stash' && (args[0] === 'clear' || args[0] === 'drop')) return `stash ${args[0]} deletes stashed work for good`;
    // `restore --staged .` only unstages; any other whole-tree restore rewrites the working files.
    const stagedOnly = (args.includes('--staged') || args.includes('-S')) && !(args.includes('--worktree') || args.includes('-W'));
    if (sub === 'restore' && wholeTree && !stagedOnly) return 'restore . throws away every uncommitted change';
  }
  return null;
}

function settingsPath(dir) {
  return path.join(dir, '.claude', 'settings.json');
}

function readSettings(file) {
  if (!fs.existsSync(file)) return {};
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function isOurs(entry) {
  return (entry.hooks || []).some((h) => (h.command || '').includes(HOOK_FILE));
}

// Real path, compared without case on Windows, so a junction or other spelling of a path still matches.
function samePath(a, b) {
  const real = (p) => (fs.existsSync(p) ? fs.realpathSync(p) : path.resolve(p));
  const [x, y] = [real(a), real(b)];
  return process.platform === 'win32' ? x.toLowerCase() === y.toLowerCase() : x === y;
}

function projectDir(arg) {
  const dir = path.resolve(arg || '.');
  if (samePath(dir, os.homedir())) {
    throw new Error('refusing to install into your home folder: the guard is per project, never global');
  }
  return dir;
}

export function install(arg) {
  const dir = projectDir(arg);
  const file = settingsPath(dir);
  const settings = readSettings(file);
  settings.hooks ??= {};
  settings.hooks.PreToolUse ??= [];
  if (!Array.isArray(settings.hooks.PreToolUse)) throw new Error(`${file}: hooks.PreToolUse is not a list; fix it by hand first`);
  if (!settings.hooks.PreToolUse.some(isOurs)) {
    settings.hooks.PreToolUse.push({ matcher: MATCHER, hooks: [{ type: 'command', command: COMMAND }] });
  }
  const agyFile = path.join(dir, '.agents', 'hooks.json');
  const agy = readSettings(agyFile);
  agy[AGY_NAME] = AGY_ENTRY;
  for (const host of ['.claude', '.agents']) {
    fs.mkdirSync(path.join(dir, host, 'hooks'), { recursive: true });
    fs.copyFileSync(fileURLToPath(import.meta.url), path.join(dir, host, 'hooks', HOOK_FILE));
  }
  fs.writeFileSync(file, `${JSON.stringify(settings, null, 2)}\n`);
  fs.writeFileSync(agyFile, `${JSON.stringify(agy, null, 2)}\n`);
  return `git guard on: ${file} (Claude Code), ${agyFile} (Antigravity)`;
}

export function remove(arg) {
  const dir = path.resolve(arg || '.');
  const file = settingsPath(dir);
  if (fs.existsSync(file)) {
    const settings = readSettings(file);
    const list = settings.hooks?.PreToolUse;
    if (list) {
      settings.hooks.PreToolUse = list.filter((e) => !isOurs(e));
      if (settings.hooks.PreToolUse.length === 0) delete settings.hooks.PreToolUse;
      if (Object.keys(settings.hooks).length === 0) delete settings.hooks;
    }
    if (Object.keys(settings).length === 0) fs.rmSync(file);
    else fs.writeFileSync(file, `${JSON.stringify(settings, null, 2)}\n`);
  }
  const agyFile = path.join(dir, '.agents', 'hooks.json');
  if (fs.existsSync(agyFile)) {
    const agy = readSettings(agyFile);
    delete agy[AGY_NAME];
    if (Object.keys(agy).length === 0) fs.rmSync(agyFile);
    else fs.writeFileSync(agyFile, `${JSON.stringify(agy, null, 2)}\n`);
  }
  for (const host of ['.claude', '.agents']) {
    fs.rmSync(path.join(dir, host, 'hooks', HOOK_FILE), { force: true });
    for (const folder of [path.join(dir, host, 'hooks'), path.join(dir, host)]) {
      if (fs.existsSync(folder) && fs.readdirSync(folder).length === 0) fs.rmdirSync(folder);
    }
  }
  return 'git guard off';
}

export function status(arg) {
  const dir = path.resolve(arg || '.');
  const claude = (readSettings(settingsPath(dir)).hooks?.PreToolUse || []).some(isOurs)
    && fs.existsSync(path.join(dir, '.claude', 'hooks', HOOK_FILE));
  const agy = Boolean(readSettings(path.join(dir, '.agents', 'hooks.json'))[AGY_NAME])
    && fs.existsSync(path.join(dir, '.agents', 'hooks', HOOK_FILE));
  if (claude && agy) return 'git guard on';
  if (!claude && !agy) return 'git guard off';
  return `git guard half on: Claude Code ${claude ? 'on' : 'off'}, Antigravity ${agy ? 'on' : 'off'}; run install again`;
}

function runHook() {
  let input = '';
  process.stdin.on('data', (d) => { input += d; });
  process.stdin.on('end', () => {
    let call;
    try { call = JSON.parse(input); } catch { process.exit(0); }
    // Antigravity sends toolCall.args.CommandLine and reads a decision on stdout; Claude Code sends tool_input.command and reads exit 2.
    const agy = Boolean(call?.toolCall);
    const reason = blockReason(agy ? call.toolCall.args?.CommandLine : call?.tool_input?.command);
    const message = reason && `BLOCKED by the project git guard: ${reason}. Ask the owner to run it, or turn the guard off: node ${agy ? '.agents' : '.claude'}/hooks/${HOOK_FILE} remove .`;
    if (agy) {
      process.stdout.write(JSON.stringify(reason ? { decision: 'deny', reason: message } : { decision: 'allow' }));
      process.exit(0);
    }
    if (!reason) process.exit(0);
    process.stderr.write(`${message}\n`);
    process.exit(2);
  });
}

if (process.argv[1] && samePath(process.argv[1], fileURLToPath(import.meta.url))) {
  const [mode, dir] = process.argv.slice(2);
  try {
    if (mode === undefined) runHook();
    else if (mode === 'install') console.log(install(dir));
    else if (mode === 'remove') console.log(remove(dir));
    else if (mode === 'status') console.log(status(dir));
    else throw new Error(`unknown mode "${mode}"; use install, remove or status, followed by the repo folder`);
  } catch (err) {
    console.error(`git guard: ${err.message}`);
    process.exit(1);
  }
}
