import { getCatalog, findPackageRoot } from './catalog.js';
import { formatPlanHuman, formatPlanJson } from './plan.js';
import { runProjectInstaller } from './interactive.js';
import { collectStatus, formatStatusHuman, formatStatusJson } from './status.js';
import { executeUpdate, formatUpdateHuman, formatUpdateJson } from './update.js';
import { executeRestore, formatRestoreHuman, formatRestoreJson } from './restore.js';
import { executeUninstall, formatUninstallHuman, formatUninstallJson } from './uninstall.js';
import {
  PURGE_CONFIRMATION_PHRASE,
  executePurge,
  formatPurgeHuman,
  formatPurgeJson,
} from './purge.js';
import { executeProjectInstall } from './transaction.js';
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
  install <skill>   Install a skill into the project (.agents/skills/<skill>)
  add <skill>       Alias for install
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
  --all             Uninstall every recorded Sigma skill in the chosen Project or Global scope
  --dry-run         Preview install, update, restore, uninstall, or purge changes without writing files
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
  --no-color        Disable color and reveal animation
  --static          Disable animation and screen repainting
  --narrow          Use the narrow-terminal layout
  -y, --yes         Skip interactive confirmations

Run without a command to start the interactive Project Installation.

Available Skills:
${skillsList}
`;
}

/**
 * Parse CLI arguments into structured options.
 *
 * @param {string[]} args
 * @returns {object}
 */
export function parseCliArgs(args) {
  const parsed = {
    command: null,
    skillId: null,
    skillIds: [],
    projectRoot: null,
    stateDir: null,
    dryRun: false,
    json: false,
    help: false,
    version: false,
    yes: false,
    global: false,
    noColor: false,
    static: false,
    narrow: false,
    method: null,
    destinations: [],
    adoptChanged: null,
    adoptLegacy: null,
    adoptUnverified: null,
    adoptMalformed: null,
    outsideEdit: null,
    malformedMarkers: null,
    clean: null,
    changed: null,
    exportDir: null,
    all: false,
    confirmPurge: undefined,
    unknown: [],
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '-h' || arg === '--help') {
      parsed.help = true;
    } else if (arg === '-v' || arg === '--version') {
      parsed.version = true;
    } else if (arg === '--all') {
      parsed.all = true;
    } else if (arg === '--dry-run') {
      parsed.dryRun = true;
    } else if (arg === '--json') {
      parsed.json = true;
    } else if (arg === '-y' || arg === '--yes') {
      parsed.yes = true;
    } else if (arg === '-g' || arg === '--global') {
      parsed.global = true;
    } else if (arg === '--no-color') {
      parsed.noColor = true;
    } else if (arg === '--static') {
      parsed.static = true;
    } else if (arg === '--narrow') {
      parsed.narrow = true;
    } else if (arg === '--copy') {
      parsed.method = parsed.method && parsed.method !== 'copy' ? 'conflict' : 'copy';
    } else if (arg === '--link') {
      parsed.method = parsed.method && parsed.method !== 'link' ? 'conflict' : 'link';
    } else if (arg === '--adopt-changed') {
      parsed.adoptChanged = args[++i];
    } else if (arg.startsWith('--adopt-changed=')) {
      parsed.adoptChanged = arg.slice('--adopt-changed='.length);
    } else if (arg === '--adopt-legacy') {
      parsed.adoptLegacy = args[++i];
    } else if (arg.startsWith('--adopt-legacy=')) {
      parsed.adoptLegacy = arg.slice('--adopt-legacy='.length);
    } else if (arg === '--adopt-unverified') {
      parsed.adoptUnverified = args[++i];
    } else if (arg.startsWith('--adopt-unverified=')) {
      parsed.adoptUnverified = arg.slice('--adopt-unverified='.length);
    } else if (arg === '--adopt-malformed') {
      parsed.adoptMalformed = args[++i];
    } else if (arg.startsWith('--adopt-malformed=')) {
      parsed.adoptMalformed = arg.slice('--adopt-malformed='.length);
    } else if (arg === '--outside-edit') {
      parsed.outsideEdit = args[++i];
    } else if (arg.startsWith('--outside-edit=')) {
      parsed.outsideEdit = arg.slice('--outside-edit='.length);
    } else if (arg === '--malformed-markers') {
      parsed.malformedMarkers = args[++i];
    } else if (arg.startsWith('--malformed-markers=')) {
      parsed.malformedMarkers = arg.slice('--malformed-markers='.length);
    } else if (arg === '--clean') {
      parsed.clean = args[++i];
    } else if (arg.startsWith('--clean=')) {
      parsed.clean = arg.slice('--clean='.length);
    } else if (arg === '--changed') {
      parsed.changed = args[++i];
    } else if (arg.startsWith('--changed=')) {
      parsed.changed = arg.slice('--changed='.length);
    } else if (arg === '--export-dir') {
      parsed.exportDir = args[++i];
    } else if (arg.startsWith('--export-dir=')) {
      parsed.exportDir = arg.slice('--export-dir='.length);
    } else if (arg === '--confirm-purge') {
      parsed.confirmPurge = args[++i] ?? '';
    } else if (arg.startsWith('--confirm-purge=')) {
      parsed.confirmPurge = arg.slice('--confirm-purge='.length);
    } else if (arg === '--destination') {
      parsed.destinations.push(args[++i]);
    } else if (arg.startsWith('--destination=')) {
      parsed.destinations.push(arg.slice('--destination='.length));
    } else if (arg === '--skill') {
      parsed.skillId = args[++i];
      if (parsed.skillId) parsed.skillIds.push(parsed.skillId);
    } else if (arg.startsWith('--skill=')) {
      parsed.skillId = arg.slice('--skill='.length);
      if (parsed.skillId) parsed.skillIds.push(parsed.skillId);
    } else if (arg === '--project' || arg === '--cwd') {
      parsed.projectRoot = args[++i];
    } else if (arg.startsWith('--project=')) {
      parsed.projectRoot = arg.slice('--project='.length);
    } else if (arg.startsWith('--cwd=')) {
      parsed.projectRoot = arg.slice('--cwd='.length);
    } else if (arg === '--state-dir') {
      parsed.stateDir = args[++i];
    } else if (arg.startsWith('--state-dir=')) {
      parsed.stateDir = arg.slice('--state-dir='.length);
    } else if (
      !parsed.command &&
      (arg === 'list' || arg === 'verify' || arg === 'check' || arg === 'install' || arg === 'add' || arg === 'status' || arg === 'update' || arg === 'restore' || arg === 'uninstall' || arg === 'purge')
    ) {
      parsed.command = arg;
    } else if (!parsed.skillId && (parsed.command === 'install' || parsed.command === 'add')) {
      parsed.skillId = arg;
    } else if ((parsed.command === 'update' || parsed.command === 'restore' || parsed.command === 'uninstall') && !arg.startsWith('-')) {
      parsed.skillIds.push(arg);
    } else if (arg === '--list') {
      parsed.command = 'list';
    } else {
      parsed.unknown.push(arg);
    }
  }

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

    const adoptFlags = [
      ['--adopt-changed', opts.adoptChanged],
      ['--adopt-legacy', opts.adoptLegacy],
      ['--adopt-unverified', opts.adoptUnverified],
      ['--adopt-malformed', opts.adoptMalformed],
    ];
    for (const [flag, value] of adoptFlags) {
      if (value && value !== 'replace' && value !== 'skip' && value !== 'export') {
        writeErr(`sigmaskills error: ${flag} must be replace, skip, or export`);
        return 1;
      }
    }

    if (opts.outsideEdit && opts.outsideEdit !== 'replace' && opts.outsideEdit !== 'skip' && opts.outsideEdit !== 'export') {
      writeErr('sigmaskills error: --outside-edit must be replace, skip, or export');
      return 1;
    }

    if (opts.malformedMarkers && opts.malformedMarkers !== 'replace' && opts.malformedMarkers !== 'skip' && opts.malformedMarkers !== 'repair') {
      writeErr('sigmaskills error: --malformed-markers must be skip, repair, or replace');
      return 1;
    }

    if (opts.clean && opts.clean !== 'remove' && opts.clean !== 'keep') {
      writeErr('sigmaskills error: --clean must be remove or keep');
      return 1;
    }

    if (opts.changed && opts.changed !== 'backup' && opts.changed !== 'keep' && opts.changed !== 'export' && opts.changed !== 'delete') {
      writeErr('sigmaskills error: --changed must be backup, keep, export, or delete');
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

    if (opts.command === 'list' || (!opts.command && opts.json && !opts.skillId)) {
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
          writeOut(`  Description: ${skill.description}\n`);
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

    if (opts.command === 'install' || opts.command === 'add' || opts.skillId) {
      if (!opts.skillId) {
        writeErr("sigmaskills error: missing required skill name for install command (e.g. 'sigmaskills install sigmawrite')");
        return 1;
      }

      if (opts.global && !opts.dryRun && !opts.yes) {
        writeErr('sigmaskills error: Global Installation requires both --global and --yes; CI, TTY, JSON, and Agent Host detection never imply that authority');
        return 1;
      }

      const env = io.env || process.env;
      const result = executeProjectInstall({
        catalog,
        skillId: opts.skillId,
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
      });

      if (opts.json) {
        writeOut(formatPlanJson(result.plan));
      } else {
        writeOut(formatPlanHuman(result.plan));
        if (!opts.dryRun) {
          writeOut('');
          for (const dest of result.plan.destinations) {
            const method = dest.method ? ` [${dest.method}]` : '';
            writeOut(`✔ Installed ${result.plan.title} (${result.plan.skill}) to ${dest.relativeDestination}${method}`);
          }
          writeOut(`  Revision: ${result.plan.sourceRevision}`);
          if (result.plan.scope !== 'global') {
            writeOut(`  Project lock: skills-lock.json updated`);
          }
        }
      }
      return 0;
    }

    if (!opts.command && !opts.skillId && !opts.dryRun && !opts.yes) {
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
