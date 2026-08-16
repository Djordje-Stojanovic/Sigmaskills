import { getCatalog, findPackageRoot } from './catalog.js';

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
  list              List all shipped skills and their Skill Revisions
  verify            Validate manifest, skill resources, and compute revisions

Options:
  -v, --version     Show version number
  -h, --help        Show help
  --json            Output in JSON format (for list command)

Available Skills:
${skillsList}
`;
}

/**
 * Main CLI entrypoint.
 *
 * @param {string[]} args Command-line arguments
 * @param {object} [io] Optional custom stdout/stderr stream handles
 * @returns {Promise<number>} Exit code (0 for success, 1 for failure)
 */
export async function runCli(args = process.argv.slice(2), io = { stdout: process.stdout, stderr: process.stderr }) {
  const writeOut = (str) => io.stdout.write(str.endsWith('\n') ? str : `${str}\n`);
  const writeErr = (str) => io.stderr.write(str.endsWith('\n') ? str : `${str}\n`);

  try {
    const rootDir = findPackageRoot();
    const catalog = getCatalog(rootDir);

    if (args.length === 0 || args.includes('-h') || args.includes('--help')) {
      writeOut(buildHelpText(catalog));
      return 0;
    }

    if (args.includes('-v') || args.includes('--version')) {
      writeOut(catalog.manifest.version);
      return 0;
    }

    if (args[0] === 'list' || args[0] === '--list' || args.includes('--json')) {
      if (args.includes('--json')) {
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

    if (args[0] === 'verify' || args[0] === 'check') {
      writeOut(`✔ Manifest verified (${catalog.manifest.name} v${catalog.manifest.version})`);
      for (const skill of catalog.skills) {
        const fileCount = Object.keys(skill.files).length;
        writeOut(`✔ Skill '${skill.id}': ${fileCount} files verified (revision ${skill.revision.slice(0, 12)}…)`);
      }
      writeOut(`\nAll ${catalog.skills.length} skills in Skill Pack validated successfully.`);
      return 0;
    }

    writeErr(`sigmaskills error: unknown option or command: ${args[0]}`);
    writeErr(`Run 'sigmaskills --help' for usage information.`);
    return 1;
  } catch (err) {
    writeErr(`sigmaskills error: ${err.message}`);
    return 1;
  }
}
