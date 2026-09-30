import path from 'node:path';
import { createInstallPlan, createProjectSkillClassifier, formatPlanHuman } from './plan.js';
import { createNeedsResolutionError, createUnownedConflictError, executeProjectInstall } from './transaction.js';
import { isDestinationOwned } from './state.js';
import {
  UNIVERSAL_PROJECT_DESTINATION,
  defaultSelectedRoots,
  findDestinationConflicts,
  listGlobalDestinationGroups,
  listProjectDestinationGroups,
  loadHostRegistry,
  resolveGlobalSkillPath,
  resolveHomeDir,
} from './destinations.js';
import { destinationRowTitle, isSearchChar, pickerItems, selectableGroups, visibleDestinationItems } from './destination-items.js';
import { recommendedLinkMethod } from './links.js';
import { EMBERFORGE_PALETTE, TerminalRenderer, isCiEnv, wrapWords } from './terminal.js';
import { KeyInput } from './key-input.js';

export { EMBERFORGE_PALETTE, isCiEnv };

function isHelpKey(key) {
  return Boolean(key && (key.ch === '?' || key.sequence === '?' || key.name === '?'));
}

function helpLines(renderer) {
  return [
    renderer.style(renderer.brand, EMBERFORGE_PALETTE.gold, true),
    'Keyboard',
    '',
    '↑/↓ move focus',
    'space toggle selection',
    'a select all skills · g global warning',
    'type to search Agent Hosts',
    'enter continue',
    'esc cancel',
    'Ctrl+C abort',
    'Plain mode: type a command, then Enter.',
    'number toggle · next/prev page · /text search · / clear',
    '? close help',
  ];
}

const PAGE_KEYS = ['next', 'prev', 'right', 'left'];

function turnPage(renderer, key) {
  const step = ['next', 'right'].includes(key.name) ? 1 : -1;
  renderer.page = Math.max(0, Math.min(renderer.pages - 1, renderer.page + step));
}

async function readKeyedScreen(renderer, input, paint) {
  renderer.page = 0;
  renderer.paint = paint;
  while (true) {
    paint();
    const key = await input.next();
    if (key.name === 'input-error') throw key.error;
    if (renderer.pages > 1 && PAGE_KEYS.includes(key.name)) {
      turnPage(renderer, key);
      continue;
    }
    if (isHelpKey(key)) {
      const closeKey = await showHelp(renderer, input);
      if (['ctrl-c', 'eof'].includes(closeKey.name)) return { help: false, key: closeKey };
      return { help: true, key };
    }
    return { help: false, key };
  }
}

async function showHelp(renderer, input) {
  const paint = () => renderer.screen(helpLines(renderer));
  renderer.paint = paint;
  renderer.page = 0;
  paint();
  while (true) {
    const key = await input.next();
    if (key.name === 'input-error') throw key.error;
    if (PAGE_KEYS.includes(key.name)) {
      turnPage(renderer, key);
      paint();
    } else return key;
  }
}

function withHelp(hints) {
  return `${hints} · ? help`;
}


function compact(value, width) {
  return value.length <= width ? value : value.slice(0, Math.max(0, width - 1)) + '…';
}

function menuLines(renderer, { heading, rows, cursor, details = [], footer, error }) {
  const width = Math.max(1, renderer.width - 1);
  const head = [compact(heading, width)];
  if (renderer.height >= 12) head.unshift(renderer.style(renderer.brand, EMBERFORGE_PALETTE.gold, true));
  const hints = width < 70
    ? (renderer.static ? '# toggle /search next/prev enter esc ?' : '↑↓ move · space · enter · esc · ?')
    : footer;
  const tail = [compact(hints, width)];
  if (error) tail.unshift(compact('Error: ' + error, width));
  if (renderer.height >= 16) tail.unshift(...details.slice(0, 3).map((line) => compact(line, width)));
  const limit = Math.max(1, Math.min(8, renderer.height - 2 - head.length - tail.length));
  const view = visibleDestinationItems(rows, cursor, limit);
  renderer.menuSize = limit;
  if (view.total > view.items.length) tail.unshift(compact(`Showing ${view.start + 1}–${view.start + view.items.length} of ${view.total}`, width));
  return [...head, ...view.items.map((row) => compact(row, width)), ...tail];
}

function pickerLines(renderer, catalog, selected, cursor, error, scope) {
  const focused = catalog.skills[cursor];
  // Wrap the short description onto at most two lines so narrow terminals show it whole.
  const summary = wrapWords(focused?.shortDescription || focused?.description || '', Math.max(1, renderer.width - 1));
  const scopeLabel = scope === 'global' ? 'Global Installation' : 'Project Installation (default)';
  return menuLines(renderer, {
    heading: `${scopeLabel} · Stage 1/4`,
    rows: catalog.skills.map((skill, index) => `${index === cursor ? '>' : ' '} ${renderer.static ? (index + 1) + '. ' : ''}[${selected.has(skill.id) ? 'x' : ' '}] ${skill.title} (${skill.id})`),
    cursor,
    details: [`Focused: ${focused?.title || ''}`, summary[0], ...(summary.length > 1 ? [summary.slice(1).join(' ')] : [])],
    footer: renderer.static ? 'number toggle · a all · g global · enter next · esc cancel · ? help' : '↑↓ move · space toggle · a all · g global · enter next · esc cancel · ? help',
    error,
  });
}

function globalWarningLines(renderer) {
  return [
    renderer.style('Global Installation warning', EMBERFORGE_PALETTE.red, true),
    '',
    'Global Installation writes skills for this operating-system user.',
    'Other projects can pick them up. Project Installation remains the safer default.',
    '',
    'Continue with Global Installation? [y/N]',
    'y continue · n/enter/esc cancel · ? help',
  ];
}

async function confirmYesNo(renderer, input, lines) {
  while (true) {
    const { help, key } = await readKeyedScreen(renderer, input, () => renderer.screen(lines()));
    if (help) continue;
    if (key.name === 'y') return { confirmed: true, exitCode: 0 };
    if (key.name === 'ctrl-c') return { confirmed: false, exitCode: 130 };
    if (key.name === 'eof' || key.name === 'escape' || key.name === 'n' || key.name === 'return') {
      return { confirmed: false, exitCode: 0 };
    }
  }
}

function confirmGlobalWarning(renderer, input) {
  return confirmYesNo(renderer, input, () => globalWarningLines(renderer));
}

async function selectSkills(renderer, input, catalog, initialScope = 'project') {
  const selected = new Set();
  let cursor = 0;
  let error = '';
  let scope = initialScope === 'global' ? 'global' : 'project';

  while (true) {
    const { help, key } = await readKeyedScreen(
      renderer,
      input,
      () => renderer.screen(pickerLines(renderer, catalog, selected, cursor, error, scope)),
    );
    if (help) continue;
    if (key.name === 'ctrl-c') return { cancelled: true, exitCode: 130 };
    if (key.name === 'escape' || key.name === 'eof') return { cancelled: true, exitCode: 0 };
    if (key.name === 'up' || (key.name === 'tab' && key.shift)) {
      cursor = (cursor + catalog.skills.length - 1) % catalog.skills.length;
    }
    if (key.name === 'down' || (key.name === 'tab' && !key.shift)) {
      cursor = (cursor + 1) % catalog.skills.length;
    }
    if (key.name === 'next') cursor = Math.min(catalog.skills.length - 1, cursor + renderer.menuSize);
    if (key.name === 'prev') cursor = Math.max(0, cursor - renderer.menuSize);
    if (key.line && /^\d+$/.test(key.name) && catalog.skills[Number(key.name) - 1]) {
      cursor = Number(key.name) - 1;
      key.name = 'space';
    }
    if (key.name === 'space') {
      const skillId = catalog.skills[cursor].id;
      if (selected.has(skillId)) selected.delete(skillId);
      else selected.add(skillId);
      error = '';
    }
    if (key.name === 'a') {
      if (selected.size === catalog.skills.length) selected.clear();
      else catalog.skills.forEach((skill) => selected.add(skill.id));
      error = '';
    }
    if (key.name === 'g' && scope !== 'global') {
      const warning = await confirmGlobalWarning(renderer, input);
      if (!warning.confirmed) return { cancelled: true, exitCode: warning.exitCode };
      scope = 'global';
      error = '';
      continue;
    }
    if (key.name === 'return') {
      if (selected.size === 0) {
        error = 'Select at least one skill.';
      } else {
        return {
          cancelled: false,
          scope,
          skillIds: catalog.skills.filter((skill) => selected.has(skill.id)).map((skill) => skill.id),
        };
      }
    }
  }
}

function persistOutput(renderer, text) {
  renderer.cleanup();
  renderer.line(text);
}

function destinationPickerLines(renderer, items, selectedRoots, cursor, query, error, scope) {
  const scopeLabel = scope === 'global' ? 'Global Installation' : 'Project Installation';
  return menuLines(renderer, {
    heading: `${scopeLabel} · Stage 2/4 · destinations`,
    rows: items.map((item, index) => `${index === cursor ? '>' : ' '} ${renderer.static ? (index + 1) + '. ' : ''}[${selectedRoots.has(item.relativeRoot) ? 'x' : ' '}] ${destinationRowTitle(item)}`),
    cursor,
    details: [query ? `Search: ${query}` : 'Only .agents/skills is selected by default.', `Selected: ${selectedRoots.size} · Path: ${items[cursor]?.absoluteRoot || '(no matches)'}`],
    footer: renderer.static ? 'number toggle · /search · next/prev · enter next · esc cancel · ? help' : '↑↓ move · type search · space toggle · enter next · esc cancel · ? help',
    error,
  });
}

async function selectDestinations(renderer, input, groups, scope = 'project') {
  const selectedRoots = new Set(defaultSelectedRoots(groups));
  let query = '';
  let cursor = 0;
  let error = '';

  while (true) {
    const items = pickerItems(groups, query);
    if (items.length === 0) cursor = 0;
    else cursor = ((cursor % items.length) + items.length) % items.length;
    const { help, key } = await readKeyedScreen(
      renderer,
      input,
      () => renderer.screen(destinationPickerLines(renderer, items, selectedRoots, cursor, query, error, scope)),
    );
    if (help) continue;
    if (key.name === 'ctrl-c') return { cancelled: true, exitCode: 130 };
    if (key.name === 'escape') {
      if (query) {
        query = '';
        cursor = 0;
        error = '';
        continue;
      }
      return { cancelled: true, exitCode: 0 };
    }
    if (key.name === 'eof') return { cancelled: true, exitCode: 0 };
    if (key.name === 'up' || (key.name === 'tab' && key.shift)) {
      if (items.length) cursor = (cursor + items.length - 1) % items.length;
    }
    if (key.name === 'down' || (key.name === 'tab' && !key.shift)) {
      if (items.length) cursor = (cursor + 1) % items.length;
    }
    if (key.name === 'next') cursor = Math.min(items.length - 1, cursor + renderer.menuSize);
    if (key.name === 'prev') cursor = Math.max(0, cursor - renderer.menuSize);
    if (key.line && /^\d+$/.test(key.name) && items[Number(key.name) - 1]) {
      cursor = Number(key.name) - 1;
      key.name = 'space';
    }
    if (key.line && key.ch.startsWith('/')) {
      query = key.ch.slice(1);
      cursor = 0;
      error = '';
      continue;
    }
    if (key.name === 'backspace') {
      query = query.slice(0, -1);
      cursor = 0;
      error = '';
    }
    if (isSearchChar(key)) {
      query += key.ch || key.name;
      cursor = 0;
      error = '';
    }
    if (key.name === 'space') {
      const item = items[cursor];
      if (item?.relativeRoot) {
        if (selectedRoots.has(item.relativeRoot)) selectedRoots.delete(item.relativeRoot);
        else selectedRoots.add(item.relativeRoot);
        error = '';
      }
    }
    if (key.name === 'return') {
      if (selectedRoots.size === 0) {
        error = 'Select at least one destination.';
      } else {
        return {
          cancelled: false,
          selectedRoots: selectableGroups(groups)
            .map((group) => group.relativeRoot)
            .filter((root) => selectedRoots.has(root)),
        };
      }
    }
  }
}

function summaryLines(renderer, plans, scope = 'project') {
  const title = scope === 'global' ? 'Confirm Global Installation' : 'Confirm Project Installation';
  const lines = [
    renderer.style(`${title} · Stage 4/4`, EMBERFORGE_PALETTE.gold, true),
    '',
    'Resolved destinations:',
  ];
  for (const plan of plans) {
    lines.push(`${plan.title} (${plan.skill})`);
    for (const dest of plan.destinations || [{ destination: plan.destination }]) {
      const method = dest.method ? ` [${dest.method}]` : '';
      for (const wrapped of wrapWords(`${dest.destination}${method}`, Math.max(20, renderer.width - 2))) {
        lines.push(`  ${wrapped}`);
      }
      if (dest.dependsOn) {
        for (const wrapped of wrapWords(`depends on ${dest.dependsOn}`, Math.max(20, renderer.width - 4))) {
          lines.push(`    ${wrapped}`);
        }
      }
      if (dest.overwrite) lines.push(`    Overwrite: ${dest.overwrite}`);
      if (dest.delete) lines.push(`    Delete: ${dest.delete}`);
      if (dest.backup) lines.push(`    Backup: ${dest.backup}`);
      if (scope === 'global') {
        const hostNames = (dest.hosts || []).map((host) => host.displayName).join(', ');
        if (hostNames) lines.push(`    Agent Hosts: ${hostNames}`);
        if (dest.method) lines.push(`    Method: ${dest.method}`);
      }
    }
  }
  lines.push('');
  lines.push(`Install ${plans.length} selected skill${plans.length === 1 ? '' : 's'}? [y/N]`);
  lines.push(withHelp('y confirm · n/enter/esc cancel'));
  return lines;
}

function methodPickerLines(renderer, cursor) {
  const linkDetail = recommendedLinkMethod() === 'junction'
    ? 'Windows directory junctions to the canonical copy'
    : 'macOS/Linux symbolic links to the canonical copy';
  const options = [
    { title: 'Link (recommended)', detail: linkDetail },
    { title: 'Copy', detail: 'Independent managed copy at every destination' },
  ];
  const lines = [
    renderer.style(renderer.brand, EMBERFORGE_PALETTE.gold, true),
    `Project Installation · method · Stage 3/4${renderer.narrow ? ' · narrow' : ''}`,
    '',
    'Choose how host-specific destinations are written. The installer never changes method silently.',
  ];
  options.forEach((option, index) => {
    const current = index === cursor ? '>' : ' ';
    const checked = index === cursor ? 'x' : ' ';
    lines.push(`${current} [${checked}] ${option.title}`);
    for (const wrapped of wrapWords(option.detail, Math.max(20, renderer.width - 6))) {
      lines.push(`      ${wrapped}`);
    }
  });
  lines.push('');
  lines.push(withHelp(renderer.static ? 'link/copy choose · enter link · esc cancel' : '↑/↓ move · enter continue · esc cancel'));
  return lines;
}

async function selectMethod(renderer, input) {
  let cursor = 0;
  while (true) {
    const { help, key } = await readKeyedScreen(renderer, input, () => renderer.screen(methodPickerLines(renderer, cursor)));
    if (help) continue;
    if (key.name === 'ctrl-c') return { cancelled: true, exitCode: 130 };
    if (key.name === 'escape' || key.name === 'eof') return { cancelled: true, exitCode: 0 };
    if (key.name === 'up' || key.name === 'down' || key.name === 'tab') cursor = cursor === 0 ? 1 : 0;
    if (key.line && ['1', '2', 'link', 'copy'].includes(key.name)) {
      return { cancelled: false, method: ['1', 'link'].includes(key.name) ? 'link' : 'copy' };
    }
    if (key.name === 'return' || key.name === 'space') {
      return { cancelled: false, method: cursor === 0 ? 'link' : 'copy' };
    }
  }
}

function fallbackLines(renderer, failure) {
  return [
    renderer.style('Link failed', EMBERFORGE_PALETTE.red, true),
    '',
    ...wrapWords(failure.relativeDestination || failure.destination || '', Math.max(20, renderer.width - 2)),
    `Cause: ${failure.cause}`,
    '',
    'The installer will not change method silently.',
    'Install a complete managed copy at this destination instead? [y/N]',
    'y copy · n/enter/esc leave unchanged · ? help',
  ];
}

async function offerCopyFallback(renderer, input, failure) {
  while (true) {
    const { help, key } = await readKeyedScreen(renderer, input, () => renderer.screen(fallbackLines(renderer, failure)));
    if (help) continue;
    if (key.name === 'y') return 'copy';
    if (key.name === 'ctrl-c') return 'ctrl-c';
    if (key.name === 'n' || key.name === 'escape' || key.name === 'return' || key.name === 'eof') {
      return 'abort';
    }
  }
}

function confirmPlans(renderer, input, plans, scope = 'project') {
  return confirmYesNo(renderer, input, () => summaryLines(renderer, plans, scope));
}

/**
 * Run the interactive Emberforge Project Installation.
 *
 * @param {object} params
 * @param {object} params.catalog
 * @param {string} params.packageRoot
 * @param {string} params.projectRoot
 * @param {string} [params.customStateDir]
 * @param {object} params.io
 * @param {object} [params.options]
 * @returns {Promise<number>}
 */
export async function runProjectInstaller(params) {
  const {
    catalog,
    packageRoot,
    projectRoot,
    customStateDir,
    io,
    options = {},
  } = params;
  const env = io.env || process.env;
  const homeDir = path.resolve(params.homeDir || resolveHomeDir(env));
  const renderer = new TerminalRenderer(io, options);
  const input = new KeyInput(io.stdin, renderer.static);

  try {
    renderer.start();
    if (params.initialScope === 'global') {
      const warning = await confirmGlobalWarning(renderer, input);
      if (!warning.confirmed) {
        persistOutput(renderer, 'Installation cancelled. No files were written.');
        return warning.exitCode;
      }
    }

    const selection = await selectSkills(renderer, input, catalog, params.initialScope === 'global' ? 'global' : 'project');
    if (selection.cancelled) {
      persistOutput(renderer, 'Installation cancelled. No files were written.');
      return selection.exitCode;
    }

    const scope = selection.scope || 'project';
    const root = scope === 'global' ? homeDir : projectRoot;
    const destinationGroups = scope === 'global'
      ? listGlobalDestinationGroups({
        registry: params.registry || loadHostRegistry(packageRoot),
        homeDir,
        env,
      })
      : listProjectDestinationGroups({
        registry: params.registry || loadHostRegistry(packageRoot),
        projectRoot,
        env,
      });
    const destinations = await selectDestinations(renderer, input, destinationGroups, scope);
    if (destinations.cancelled) {
      persistOutput(renderer, 'Installation cancelled. No files were written.');
      return destinations.exitCode;
    }

    const hostSelected = destinations.selectedRoots.some((selectedRoot) => selectedRoot !== UNIVERSAL_PROJECT_DESTINATION);
    let method = hostSelected ? 'link' : 'copy';
    if (hostSelected) {
      const methodChoice = await selectMethod(renderer, input);
      if (methodChoice.cancelled) {
        persistOutput(renderer, 'Installation cancelled. No files were written.');
        return methodChoice.exitCode;
      }
      method = methodChoice.method;
    }

    const classify = createProjectSkillClassifier({
      catalog,
      projectRoot: root,
      customStateDir,
      scope,
      homeDir,
    });
    const conflictErrors = findDestinationConflicts({
      projectRoot: root,
      skillIds: selection.skillIds,
      selectedRoots: destinations.selectedRoots,
      isOwned: (skillId, destination) => isDestinationOwned(root, skillId, destination, customStateDir, { scope }),
      classify,
      resolvePath: scope === 'global' ? resolveGlobalSkillPath : undefined,
    });
    if (conflictErrors.length > 0) {
      throw new Error(conflictErrors[0]);
    }

    const plans = selection.skillIds.map((skillId) => createInstallPlan(catalog, {
      skillId,
      projectRoot,
      homeDir,
      scope,
      customStateDir,
      packageRoot,
      selectedRoots: destinations.selectedRoots,
      destinationGroups,
      env,
      method,
    }));
    const conflict = plans.find((plan) => plan.unownedConflict);
    if (conflict) throw createUnownedConflictError(conflict);
    const pending = plans.find((plan) => plan.requiresApproval);
    if (pending) {
      renderer.cleanup();
      for (const plan of plans) {
        renderer.line(formatPlanHuman(plan));
      }
      throw createNeedsResolutionError(pending);
    }

    const confirmation = await confirmPlans(renderer, input, plans, scope);
    if (!confirmation.confirmed) {
      persistOutput(renderer, 'Installation cancelled. No files were written.');
      return confirmation.exitCode;
    }

    renderer.cleanup();

    const copyRoots = [];
    let installedCount = 0;
    for (const skillId of selection.skillIds) {
      let result;
      while (true) {
        try {
          result = executeProjectInstall({
            catalog,
            skillId,
            projectRoot,
            homeDir,
            scope,
            customStateDir,
            packageRoot,
            selectedRoots: destinations.selectedRoots,
            destinationGroups,
            env,
            method,
            copyRoots,
            createLink: params.createLink,
          });
          break;
        } catch (err) {
          if (!err.linkFailure) throw err;
          const decision = await offerCopyFallback(renderer, input, err.linkFailure);
          if (decision !== 'copy') {
            persistOutput(renderer, installedCount
              ? `Installation stopped. ${installedCount} previously installed skill(s) remain installed; the failed skill was rolled back.`
              : 'Installation cancelled. No files were written.');
            return decision === 'ctrl-c' ? 130 : 0;
          }
          copyRoots.push(err.linkFailure.relativeRoot);
        }
      }
      for (const dest of result.plan.destinations) {
        const methodLabel = dest.method ? ` [${dest.method}]` : '';
        renderer.line(`Installed ${result.plan.title} (${result.plan.skill}) to ${dest.destination}${methodLabel}`);
      }
      installedCount += 1;
    }
    const doneLabel = scope === 'global' ? 'Global Installation' : 'Project Installation';
    renderer.line(`${doneLabel} complete: ${selection.skillIds.length} skill${selection.skillIds.length === 1 ? '' : 's'} installed.`);
    return 0;
  } finally {
    input.close();
    renderer.cleanup();
  }
}
