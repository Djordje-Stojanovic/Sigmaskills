import { getCatalog, findPackageRoot } from './catalog.js';
import { formatPlanHuman, formatPlanJson } from './plan.js';
import { runProjectInstaller } from './interactive.js';
import { executeProjectInstall } from './transaction.js';

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
  list              List all shipped skills and their Skill Revisions
  verify            Validate manifest, skill resources, and compute revisions

Options:
  -v, --version     Show version number
  -h, --help        Show help
  --skill <name>    Skill identifier to install
  --dry-run         Preview installation changes without writing files
  --json            Output in versioned JSON format
  --project <path>  Target project root directory (defaults to current directory)
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
    projectRoot: null,
    stateDir: null,
    dryRun: false,
    json: false,
    help: false,
    version: false,
    yes: false,
    noColor: false,
    static: false,
    narrow: false,
    method: null,
    destinations: [],
    adoptChanged: null,
    adoptLegacy: null,
    adoptUnverified: null,
    adoptMalformed: null,
    exportDir: null,
    unknown: [],
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '-h' || arg === '--help') {
      parsed.help = true;
    } else if (arg === '-v' || arg === '--version') {
      parsed.version = true;
    } else if (arg === '--dry-run') {
      parsed.dryRun = true;
    } else if (arg === '--json') {
      parsed.json = true;
    } else if (arg === '-y' || arg === '--yes') {
      parsed.yes = true;
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
    } else if (arg === '--export-dir') {
      parsed.exportDir = args[++i];
    } else if (arg.startsWith('--export-dir=')) {
      parsed.exportDir = arg.slice('--export-dir='.length);
    } else if (arg === '--destination') {
      parsed.destinations.push(args[++i]);
    } else if (arg.startsWith('--destination=')) {
      parsed.destinations.push(arg.slice('--destination='.length));
    } else if (arg === '--skill') {
      parsed.skillId = args[++i];
    } else if (arg.startsWith('--skill=')) {
      parsed.skillId = arg.slice('--skill='.length);
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
      (arg === 'list' || arg === 'verify' || arg === 'check' || arg === 'install' || arg === 'add')
    ) {
      parsed.command = arg;
    } else if (!parsed.skillId && (parsed.command === 'install' || parsed.command === 'add')) {
      parsed.skillId = arg;
    } else if (arg === '--list') {
      parsed.command = 'list';
    } else {
      parsed.unknown.push(arg);
    }
  }

  return parsed;
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

      const result = executeProjectInstall({
        catalog,
        skillId: opts.skillId,
        projectRoot: opts.projectRoot,
        customStateDir: opts.stateDir,
        packageRoot: rootDir,
        dryRun: opts.dryRun,
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
          writeOut(`  Project lock: skills-lock.json updated`);
        }
      }
      return 0;
    }

    if (!opts.command && !opts.skillId && !opts.dryRun && !opts.yes) {
      return await runProjectInstaller({
        catalog,
        packageRoot: rootDir,
        projectRoot: opts.projectRoot || process.cwd(),
        customStateDir: opts.stateDir,
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
