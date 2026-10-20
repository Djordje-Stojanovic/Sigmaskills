import fs from 'node:fs';
import path from 'node:path';
import { UNIVERSAL_PROJECT_DESTINATION, searchHosts } from './destinations.js';

/** Short names people type for an Agent Host. The host registry ids stay the source of truth. */
export const AGENT_ALIASES = Object.freeze({
  claude: 'claude-code',
  gemini: 'gemini-cli',
  agy: 'antigravity-cli',
  antigravity: 'antigravity',
  copilot: 'github-copilot',
  kimi: 'kimi-code-cli',
  gpt: 'codex',
  openai: 'codex',
});

/**
 * Turn friendly Agent Host names into destination roots.
 *
 * A name matches a host id, its display name, a registry alias, or a short alias such as
 * `claude` or `agy`. Hosts that read `.agents/skills` need no folder of their own: the
 * universal root is always part of the result.
 *
 * @param {string[]} names
 * @param {object[]} groups destination groups for the scope (project or global)
 * @returns {{ roots: string[], hosts: object[], unknown: string[] }}
 */
export function resolveAgentRoots(names, groups) {
  const roots = new Set([UNIVERSAL_PROJECT_DESTINATION]);
  const hosts = [];
  const unknown = [];
  const all = searchHosts(groups, '');
  for (const raw of names) {
    for (const part of String(raw).split(',')) {
      const name = part.trim().toLowerCase();
      if (!name) continue;
      if (name === '*' || name === 'all') {
        all.forEach((host) => {
          if (host.relativeRoot) roots.add(host.relativeRoot);
          hosts.push(host);
        });
        continue;
      }
      const wanted = AGENT_ALIASES[name] || name;
      const exact = all.filter((host) => [host.id, host.name, host.displayName, ...(host.aliases || [])]
        .some((value) => String(value || '').toLowerCase() === wanted));
      if (exact.length === 0) {
        unknown.push(part.trim());
        continue;
      }
      for (const host of exact) {
        hosts.push(host);
        if (host.relativeRoot) roots.add(host.relativeRoot);
      }
    }
  }
  return { roots: [...roots], hosts, unknown };
}

/** Closest host ids for an unknown name, for the error message. */
export function suggestAgents(name, groups, limit = 4) {
  const needle = String(name).toLowerCase();
  return searchHosts(groups, needle).slice(0, limit).map((host) => host.id);
}

/**
 * The hosts people actually use, in the order the wizard shows them. `markers` are folders in
 * the user's home that show the host is installed on this machine.
 */
export const POPULAR_AGENTS = Object.freeze([
  { id: 'claude-code', markers: ['.claude'] },
  { id: 'codex', markers: ['.codex'] },
  { id: 'gemini-cli', markers: ['.gemini'] },
  { id: 'antigravity-cli', markers: ['.antigravity', '.gemini/antigravity'] },
  { id: 'pi', markers: ['.pi'] },
  { id: 'cursor', markers: ['.cursor'] },
  { id: 'opencode', markers: ['.config/opencode', '.opencode'] },
  { id: 'github-copilot', markers: ['.copilot'] },
  { id: 'kimi-code-cli', markers: ['.kimi'] },
  { id: 'windsurf', markers: ['.codeium/windsurf'] },
]);

/** Ids of popular hosts whose marker folder exists in the home folder. */
export function detectPopularAgents(homeDir, exists = (target) => fs.existsSync(target)) {
  return new Set(POPULAR_AGENTS
    .filter((agent) => agent.markers.some((marker) => exists(path.join(homeDir, ...marker.split('/')))))
    .map((agent) => agent.id));
}

/**
 * Short host names per destination root, for the "where" block of a summary:
 * `{ '.claude/skills': 'Claude Code', '.agents/skills': 'Codex, Cursor, Gemini CLI +21' }`.
 */
export function describeRoots(groups) {
  const names = new Map();
  for (const group of groups) {
    if (!group.relativeRoot) continue;
    const rank = (host) => {
      const index = POPULAR_AGENTS.findIndex((agent) => agent.id === host.id);
      return index === -1 ? 99 : index;
    };
    const ordered = [...group.hosts].sort((a, b) => rank(a) - rank(b));
    const shown = ordered.slice(0, 4).map((host) => host.displayName);
    const extra = group.hosts.length - shown.length;
    names.set(group.relativeRoot, `${shown.join(', ')}${extra > 0 ? ` +${extra}` : ''}`);
  }
  return names;
}
