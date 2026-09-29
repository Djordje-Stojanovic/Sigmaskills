import { getCatalog, findPackageRoot } from './catalog.js';
import { formatPlanHuman, formatPlanJson } from './plan.js';
import { runProjectInstaller } from './interactive.js';
import { collectStatus, formatStatusHuman, formatStatusJson } from './status.js';
import { executeUpdate, formatUpdateHuman, formatUpdateJson } from './update.js';
import { FOREIGN_LOCK_NOTICE } from './project-lock.js';
import { executeRestore, formatRestoreHuman, formatRestoreJson } from './restore.js';
import { executeUninstall, formatUninstallHuman, formatUninstallJson } from './uninstall.js';
import {
  PURGE_CONFIRMATION_PHRASE,
  executePurge,
  formatPurgeHuman,
  formatPurgeJson,
} from './purge.js';
import { executeProjectInstall, executeProjectInstallBatch } from './transaction.js';
import { resolveHomeDir } from './destinations.js';

/**
 * Format and print help message.
 *
 * @param {object} catalog
 * @returns {string}
 */
export function buildHelpText(catalog) {
  const version = catalog.manifest.version;
  const skillsList = catalog.skills
    .map((s) => `  - ${s.id.padEnd(18)} ${s.title.padEnd(20)} (${s.revision.slice(0, 8)}…)`)
    .join('\n');

  return `sigmaskills v${version}
Portable Agent Skills monorepo and first-party Sigma Installer

Usage:
  sigmaskills [options] [command]

Commands:
  install <skill...> Install one or more skills in one transaction (.agents/skills/<skill>)
  add <skill...>    Alias for install
  update            Update selected whole skills to the running CLI Release
  restore           Restore the latest retained backup for a skill
  uninstall         Uninstall selected skills or every recorded skill in one scope after Uninstall Review
  purge             Remove all Sigma-owned content in one scope after the typed confirmation phrase
  status            Report managed Project or Global Installation state and drift
  list              List all shipped skills and their Skill Revisions
  verify            Validate manifest, skill resources, and compute revisions

Options:
  -v, --version     Show version number
  -h, --help        Show help
  --skill <name>    Skill identifier to install, update, restore, or uninstall (repeatable)
  --all             Install every shipped skill, or uninstall every recorded Sigma skill in the chosen scope
  --dry-run         Preview install, update, restore, uninstall, or purge without writing files
  --confirm-purge <phrase>
                    Exact typed confirmation for purge; --yes, CI, non-TTY, and JSON are not enough
  --json            Output in versioned JSON format
  --project <path>  Target project root directory (defaults to current directory)
  --global          User-level Global Installation (requires --yes to write)
  --state-dir <dir> Custom state directory for private machine state
  --destination <dir> Project destination root (repeatable; default .agents/skills)
  --link            Recommended links: Windows junctions, macOS/Linux symbolic links
  --copy            Independent managed copy at every selected destination
  --adopt-changed <replace|skip|export>
                    Resolve changed owned or drifted trees
  --adopt-legacy <replace|skip|export>
                    Resolve trees that match a bundled historical baseline
  --adopt-unverified <replace|skip|export>
                    Resolve Sigma-looking trees without a baseline
  --adopt-malformed <replace|skip|export>
                    Resolve trees with malformed customization markers
  --outside-edit <replace|skip|export>
                    Resolve outside-customization edits during update
  --malformed-markers <skip|repair|replace>
                    Resolve malformed customization markers during update
  --clean <remove|keep>
                    Uninstall Review choice for a clean skill
  --changed <backup|keep|export|delete>
                    Uninstall Review choice for a changed, customized, or malformed skill
  --export-dir <dir>
                    Collision-safe destination root for export resolutions
  --no-color        Use plain, line-based prompts without color
  --static          Use paged line prompts without screen repainting
  --narrow          Use the narrow-terminal layout
  -y, --yes         Skip interactive confirmations

Run without a command to start the interactive Project Installation.

Available Skills:
${skillsList}
`;
}

const COMMANDS = ['list', 'verify', 'check', 'install', 'add', 'status', 'update', 'restore', 'uninstall', 'purge'];
const SKILL_COMMANDS = ['install', 'add', 'update', 'restore', 'uninstall'];
const RESOLUTIONS = ['replace', 'skip', 'export'];

/**
 * Every CLI flag. A flag with `value` takes the next argument (or `--flag=value`);
 * `values` lists the allowed values; `repeatable` collects every value in an array.
 */
const FLAGS = [
  { name: '--help', alias: '-h', key: 'help' },
  { name: '--version', alias: '-v', key: 'version' },
  { name: '--all', key: 'all' },
  { name: '--dry-run', key: 'dryRun' },
  { name: '--json', key: 'json' },
  { name: '--yes', alias: '-y', key: 'yes' },
  { name: '--global', alias: '-g', key: 'global' },
  { name: '--no-color', key: 'noColor' },
  { name: '--static', key: 'static' },
  { name: '--narrow', key: 'narrow' },
  { name: '--copy', key: 'copy' },
  { name: '--link', key: 'link' },
  { name: '--list', key: 'list' },
  { name: '--skill', key: 'skillIds', value: true, repeatable: true },
  { name: '--destination', key: 'destinations', value: true, repeatable: true },
  { name: '--project', alias: '--cwd', key: 'projectRoot', value: true },
  { name: '--state-dir', key: 'stateDir', value: true },
  { name: '--export-dir', key: 'exportDir', value: true },
  { name: '--adopt-changed', key: 'adoptChanged', value: true, values: RESOLUTIONS },
  { name: '--adopt-legacy', key: 'adoptLegacy', value: true, values: RESOLUTIONS },
  { name: '--adopt-unverified', key: 'adoptUnverified', value: true, values: RESOLUTIONS },
  { name: '--adopt-malformed', key: 'adoptMalformed', value: true, values: RESOLUTIONS },
  { name: '--outside-edit', key: 'outsideEdit', value: true, values: RESOLUTIONS },
  { name: '--malformed-markers', key: 'malformedMarkers', value: true, values: ['skip', 'repair', 'replace'] },
  { name: '--clean', key: 'clean', value: true, values: ['remove', 'keep'] },
  { name: '--changed', key: 'changed', value: true, values: ['backup', 'keep', 'export', 'delete'] },
  { name: '--confirm-purge', key: 'confirmPurge', value: true, allowEmpty: true },
];

function formatChoices(values) {
  return values.length === 2
    ? values.join(' or ')
    : `${values.slice(0, -1).join(', ')}, or ${values[values.length - 1]}`;
}

function readFlagValue(flag, value) {
  if (value === undefined || (value === '' && !flag.allowEmpty)) {
    throw new Error(`${flag.name} requires a value`);
  }
  if (flag.values && !flag.values.includes(value)) {
    throw new Error(`${flag.name} must be ${formatChoices(flag.values)}`);
  }
  return value;
}

/**
 * Parse CLI arguments into structured options.
 * Throws when a value flag has a missing, dash-prefixed, or disallowed value.
 *
 * @param {string[]} args
 * @returns {object}
 */
export function parseCliArgs(args) {
  const parsed = {
    command: null,
    skillIds: [],
    destinations: [],
    unknown: [],
  };
  for (const flag of FLAGS) {
    if (!(flag.key in parsed)) parsed[flag.key] = flag.value ? null : false;
  }
  parsed.confirmPurge = undefined;

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    const eq = arg.startsWith('--') ? arg.indexOf('=') : -1;
    const name = eq === -1 ? arg : arg.slice(0, eq);
    const flag = FLAGS.find((item) => item.name === name || item.alias === name);

    if (flag && flag.value) {
      let value;
      if (eq !== -1) {
        value = arg.slice(eq + 1);
      } else if (args[i + 1] !== undefined && !args[i + 1].startsWith('-')) {
        value = args[++i];
      }
      value = readFlagValue(flag, value);
      if (flag.repeatable) parsed[flag.key].push(value);
      else parsed[flag.key] = value;
    } else if (flag && eq === -1) {
      parsed[flag.key] = true;
    } else if (!parsed.command && COMMANDS.includes(arg)) {
      parsed.command = arg;
    } else if (SKILL_COMMANDS.includes(parsed.command) && !arg.startsWith('-')) {
      parsed.skillIds.push(arg);
    } else {
      parsed.unknown.push(arg);
    }
  }

  if (parsed.list) parsed.command = 'list';
  parsed.method = parsed.copy && parsed.link ? 'conflict' : parsed.copy ? 'copy' : parsed.link ? 'link' : null;
  return parsed;
}

function readStdinLine(stdin) {
  return new Promise((resolve) => {
    if (!stdin) {
      resolve('');
      return;
    }
    let settled = false;
    let buffer = '';
    const finish = () => {
      if (settled) return;
      settled = true;
      stdin.off('data', onData);
      stdin.off('end', finish);
      if (typeof stdin.pause === 'function') stdin.pause();
      resolve(buffer.split(/\r?\n/)[0] ?? '');
    };
    const onData = (chunk) => {
      buffer += String(chunk);
      if (buffer.includes('\n') || buffer.includes('\r')) finish();
    };
    stdin.on('data', onData);
    stdin.once('end', finish);
    if (typeof stdin.resume === 'function') stdin.resume();
  });
}

/**
 * Main CLI entrypoint.
 *
 * @param {string[]} args Command-line arguments
 * @param {object} [io] Optional custom stdin/stdout/stderr stream handles
 * @returns {Promise<number>} Exit code (0 for success, 1 for failure)
 */
export async function runCli(args = process.argv.slice(2), io = { stdout: process.stdout, stderr: process.stderr }) {
  const writeOut = (str) => io.stdout.write(str.endsWith('\n') ? str : `${str}\n`);
  const writeErr = (str) => io.stderr.write(str.endsWith('\n') ? str : `${str}\n`);

  try {
    const opts = parseCliArgs(args);
    const rootDir = findPackageRoot();
    const catalog = getCatalog(rootDir);

    if (opts.help) {
      writeOut(buildHelpText(catalog));
      return 0;
    }

    if (opts.version) {
      writeOut(catalog.manifest.version);
      return 0;
    }

    if (opts.unknown.length > 0) {
      writeErr(`sigmaskills error: unknown option or command: ${opts.unknown[0]}`);
      writeErr(`Run 'sigmaskills --help' for usage information.`);
      return 1;
    }

    if (opts.method === 'conflict') {
      writeErr('sigmaskills error: use either --link or --copy, not both');
      return 1;
    }

    const installing = opts.command === 'install' || opts.command === 'add' || (!opts.command && opts.skillIds.length > 0);
    const knownIds = catalog.skills.map((skill) => skill.id)
      .concat(installing ? [] : catalog.manifest.retired || []);
    const unknownId = opts.skillIds.find((id) => !knownIds.includes(id));
    if (unknownId !== undefined) {
      writeErr(`sigmaskills error: unknown skill '${unknownId}'`);
      writeErr(`The skill '${unknownId}' was not found in Skill Pack ${catalog.manifest.name}. Run 'sigmaskills list' to see skill ids.`);
      return 1;
    }

    if (opts.command === 'purge') {
      const env = io.env || process.env;
      const stdin = io.stdin || process.stdin;
      let confirmPurge = opts.confirmPurge;
      if (!opts.dryRun && confirmPurge === undefined) {
        const ci = env.CI;
        const nonInteractive = Boolean(opts.json)
          || (ci !== undefined && ci !== '' && ci !== '0' && String(ci).toLowerCase() !== 'false')
          || !stdin.isTTY;
        if (nonInteractive) {
          writeErr('sigmaskills error: purge requires --confirm-purge with the typed confirmation phrase; --yes, CI, non-TTY, and JSON are not authority');
          return 1;
        }
        writeOut(formatPurgeHuman(executePurge({
          catalog,
          projectRoot: opts.projectRoot || process.cwd(),
          homeDir: resolveHomeDir(env),
          scope: opts.global ? 'global' : 'project',
          customStateDir: opts.stateDir,
          packageRoot: rootDir,
          dryRun: true,
          env,
        })));
        writeOut(`Type ${PURGE_CONFIRMATION_PHRASE} to purge, or nothing to cancel.`);
        confirmPurge = await readStdinLine(stdin);
      }
      const result = executePurge({
        catalog,
        projectRoot: opts.projectRoot || process.cwd(),
        homeDir: resolveHomeDir(env),
        scope: opts.global ? 'global' : 'project',
        customStateDir: opts.stateDir,
        packageRoot: rootDir,
        dryRun: opts.dryRun,
        env,
        confirmPurge,
      });
      writeOut(opts.json ? formatPurgeJson(result) : formatPurgeHuman(result));
      return 0;
    }

    if (opts.command === 'update') {
      const env = io.env || process.env;
      if (opts.global && !opts.dryRun && !opts.yes) {
        writeErr('sigmaskills error: Global Installation requires both --global and --yes; CI, TTY, JSON, and Agent Host detection never imply that authority');
        return 1;
      }
      if (!opts.dryRun && !opts.yes && opts.skillIds.length === 0) {
        writeErr('sigmaskills error: update requires --yes to apply all changed skills, or --skill <id> to select complete skills; use --dry-run to preview');
        return 1;
      }
      const result = executeUpdate({
        catalog,
        projectRoot: opts.projectRoot || process.cwd(),
        homeDir: resolveHomeDir(env),
        scope: opts.global ? 'global' : 'project',
        customStateDir: opts.stateDir,
        packageRoot: rootDir,
        dryRun: opts.dryRun,
        env,
        skillIds: opts.skillIds,
        outsideEdit: opts.outsideEdit || undefined,
        malformedMarkers: opts.malformedMarkers || undefined,
        exportDir: opts.exportDir || undefined,
      });
      writeOut(opts.json ? formatUpdateJson(result) : formatUpdateHuman(result));
      return 0;
    }

    if (opts.command === 'uninstall') {
      const env = io.env || process.env;
      if (opts.global && !opts.dryRun && !opts.yes) {
        writeErr('sigmaskills error: Global Installation requires both --global and --yes; CI, TTY, JSON, and Agent Host detection never imply that authority');
        return 1;
      }
      if (opts.all && opts.skillIds.length > 0) {
        writeErr('sigmaskills error: uninstall --all cannot be combined with --skill');
        return 1;
      }
      if (opts.skillIds.length === 0 && !opts.all) {
        writeErr('sigmaskills error: uninstall requires --skill <id> or --all');
        return 1;
      }
      if (!opts.dryRun && !opts.yes) {
        writeErr('sigmaskills error: uninstall requires --yes to apply, or --dry-run to preview');
        return 1;
      }
      const result = executeUninstall({
        catalog,
        projectRoot: opts.projectRoot || process.cwd(),
        homeDir: resolveHomeDir(env),
        scope: opts.global ? 'global' : 'project',
        customStateDir: opts.stateDir,
        packageRoot: rootDir,
        dryRun: opts.dryRun,
        env,
        skillIds: opts.skillIds,
        all: opts.all,
        yes: opts.yes,
        clean: opts.clean || (opts.yes || opts.all ? 'remove' : undefined),
        changed: opts.changed || (opts.all ? 'backup' : undefined),
        exportDir: opts.exportDir || undefined,
      });
      writeOut(opts.json ? formatUninstallJson(result) : formatUninstallHuman(result));
      if ((result.summary?.failed || []).length > 0) return 1;
      return 0;
    }

    if (opts.command === 'restore') {
      const env = io.env || process.env;
      if (opts.global && !opts.dryRun && !opts.yes) {
        writeErr('sigmaskills error: Global Installation requires both --global and --yes; CI, TTY, JSON, and Agent Host detection never imply that authority');
        return 1;
      }
      if (opts.skillIds.length === 0) {
        writeErr('sigmaskills error: restore requires --skill <id>');
        return 1;
      }
      if (!opts.dryRun && !opts.yes) {
        writeErr('sigmaskills error: restore requires --yes to apply, or --dry-run to preview');
        return 1;
      }
      const result = executeRestore({
        catalog,
        projectRoot: opts.projectRoot || process.cwd(),
        homeDir: resolveHomeDir(env),
        scope: opts.global ? 'global' : 'project',
        customStateDir: opts.stateDir,
        packageRoot: rootDir,
        dryRun: opts.dryRun,
        env,
        skillIds: opts.skillIds,
        yes: opts.yes,
      });
      writeOut(opts.json ? formatRestoreJson(result) : formatRestoreHuman(result));
      return 0;
    }

    if (opts.command === 'status') {
      const env = io.env || process.env;
      const report = collectStatus({
        catalog,
        projectRoot: opts.projectRoot || process.cwd(),
        homeDir: resolveHomeDir(env),
        scope: opts.global ? 'global' : 'project',
        customStateDir: opts.stateDir,
        packageRoot: rootDir,
        env,
      });
      writeOut(opts.json ? formatStatusJson(report) : formatStatusHuman(report));
      return 0;
    }

    if (opts.command === 'list' || (!opts.command && opts.json && opts.skillIds.length === 0)) {
      if (opts.json) {
        const payload = {
          name: catalog.manifest.name,
          version: catalog.manifest.version,
          schemaVersion: catalog.manifest.schemaVersion,
          skills: catalog.skills.map((s) => ({
            id: s.id,
            title: s.title,
            description: s.description,
            revision: s.revision,
            files: s.files,
          })),
        };
        writeOut(JSON.stringify(payload, null, 2));
      } else {
        writeOut(`Skill Pack: ${catalog.manifest.name} v${catalog.manifest.version}\n`);
        for (const skill of catalog.skills) {
          writeOut(`• ${skill.title} (${skill.id})`);
          writeOut(`  Revision: ${skill.revision}`);
          writeOut(`  Description: ${skill.shortDescription}\n`);
        }
      }
      return 0;
    }

    if (opts.command === 'verify' || opts.command === 'check') {
      writeOut(`✔ Manifest verified (${catalog.manifest.name} v${catalog.manifest.version})`);
      for (const skill of catalog.skills) {
        const fileCount = Object.keys(skill.files).length;
        writeOut(`✔ Skill '${skill.id}': ${fileCount} files verified (revision ${skill.revision.slice(0, 12)}…)`);
      }
      writeOut(`\nAll ${catalog.skills.length} skills in Skill Pack validated successfully.`);
      return 0;
    }

    if (opts.command === 'install' || opts.command === 'add' || opts.skillIds.length > 0) {
      if (opts.all && opts.skillIds.length > 0) {
        writeErr('sigmaskills error: install --all cannot be combined with skill ids');
        return 1;
      }
      if (!opts.all && opts.skillIds.length === 0) {
        writeErr("sigmaskills error: missing required skill name for install command (e.g. 'sigmaskills install sigmawrite', or --all)");
        return 1;
      }

      if (opts.global && !opts.dryRun && !opts.yes) {
        writeErr('sigmaskills error: Global Installation requires both --global and --yes; CI, TTY, JSON, and Agent Host detection never imply that authority');
        return 1;
      }

      const env = io.env || process.env;
      const skillIds = opts.all ? catalog.skills.map((skill) => skill.id) : [...new Set(opts.skillIds)];
      const installParams = {
        catalog,
        projectRoot: opts.projectRoot,
        homeDir: resolveHomeDir(env),
        scope: opts.global ? 'global' : 'project',
        customStateDir: opts.stateDir,
        packageRoot: rootDir,
        dryRun: opts.dryRun,
        env,
        selectedRoots: opts.destinations.length > 0 ? opts.destinations : undefined,
        method: opts.method || undefined,
        adoptChanged: opts.adoptChanged || undefined,
        adoptLegacy: opts.adoptLegacy || undefined,
        adoptUnverified: opts.adoptUnverified || undefined,
        adoptMalformed: opts.adoptMalformed || undefined,
        exportDir: opts.exportDir || undefined,
      };
      const results = skillIds.length === 1
        ? [executeProjectInstall({ ...installParams, skillId: skillIds[0] })]
        : executeProjectInstallBatch({ ...installParams, skillIds });

      if (opts.json) {
        writeOut(results.length === 1
          ? formatPlanJson(results[0].plan)
          : JSON.stringify({ schemaVersion: 1, plans: results.map((result) => result.plan) }, null, 2));
      } else {
        for (const result of results) writeOut(formatPlanHuman(result.plan));
        if (!opts.dryRun) {
          writeOut('');
          for (const { plan } of results) {
            for (const dest of plan.destinations) {
              const method = dest.method ? ` [${dest.method}]` : '';
              writeOut(`✔ Installed ${plan.title} (${plan.skill}) to ${dest.relativeDestination}${method}`);
            }
            writeOut(`  Revision: ${plan.sourceRevision}`);
          }
          if (results.some((result) => result.lockLeftAlone)) {
            writeOut(`  ${FOREIGN_LOCK_NOTICE}`);
          } else if (results[0].plan.scope !== 'global') {
            writeOut(`  Project lock: skills-lock.json updated`);
          }
        }
      }
      return 0;
    }

    if (!opts.command && opts.skillIds.length === 0 && !opts.dryRun && !opts.yes) {
      return await runProjectInstaller({
        catalog,
        packageRoot: rootDir,
        projectRoot: opts.projectRoot || process.cwd(),
        homeDir: resolveHomeDir(io.env || process.env),
        customStateDir: opts.stateDir,
        initialScope: opts.global ? 'global' : 'project',
        io: {
          stdin: io.stdin || process.stdin,
          stdout: io.stdout,
          stderr: io.stderr,
          env: io.env || process.env,
        },
        options: {
          noColor: opts.noColor,
          static: opts.static,
          narrow: opts.narrow,
          json: opts.json,
        },
      });
    }

    writeErr(`sigmaskills error: unknown option or command`);
    writeErr(`Run 'sigmaskills --help' for usage information.`);
    return 1;
  } catch (err) {
    writeErr(`sigmaskills error: ${err.message}`);
    if (err.linkFailure) {
      writeErr(`Link failed for '${err.linkFailure.relativeDestination || err.linkFailure.destination}'.`);
      writeErr('The installer did not change method. Re-run with --copy to install a complete managed copy at this destination.');
    }
    return 1;
  }
}
