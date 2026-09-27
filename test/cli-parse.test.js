import assert from 'node:assert/strict';
import test from 'node:test';
import { buildHelpText, parseCliArgs } from '../src/cli.js';
import { findPackageRoot, getCatalog } from '../src/catalog.js';

// One case per flag that --help prints. Each case parses the flag and checks the field it sets.
const FLAG_CASES = {
  '-v': [['-v'], { version: true }],
  '--version': [['--version'], { version: true }],
  '-h': [['-h'], { help: true }],
  '--help': [['--help'], { help: true }],
  '--skill': [['update', '--skill', 'sigmawrite', '--skill=sigmabrief'], { skillIds: ['sigmawrite', 'sigmabrief'] }],
  '--all': [['uninstall', '--all'], { all: true }],
  '--dry-run': [['--dry-run'], { dryRun: true }],
  '--confirm-purge': [['purge', '--confirm-purge', 'purge SigmaSkills'], { confirmPurge: 'purge SigmaSkills' }],
  '--write-identities': [['release', '--write-identities'], { writeIdentities: true }],
  '--expected-commit': [['release', '--expected-commit=deadbeef'], { expectedCommit: 'deadbeef' }],
  '--expected-version': [['release', '--expected-version', '0.2.0'], { expectedVersion: '0.2.0' }],
  '--expected-digest': [['release', '--expected-digest', 'ab'], { expectedDigest: 'ab' }],
  '--json': [['--json'], { json: true }],
  '--project': [['--project', 'app'], { projectRoot: 'app' }],
  '--global': [['--global'], { global: true }],
  '--state-dir': [['--state-dir', 'state'], { stateDir: 'state' }],
  '--destination': [['--destination', '.claude/skills', '--destination=.pi/skills'], { destinations: ['.claude/skills', '.pi/skills'] }],
  '--link': [['--link'], { method: 'link' }],
  '--copy': [['--copy'], { method: 'copy' }],
  '--adopt-changed': [['--adopt-changed', 'replace'], { adoptChanged: 'replace' }],
  '--adopt-legacy': [['--adopt-legacy=skip'], { adoptLegacy: 'skip' }],
  '--adopt-unverified': [['--adopt-unverified', 'export'], { adoptUnverified: 'export' }],
  '--adopt-malformed': [['--adopt-malformed', 'skip'], { adoptMalformed: 'skip' }],
  '--outside-edit': [['--outside-edit', 'skip'], { outsideEdit: 'skip' }],
  '--malformed-markers': [['--malformed-markers', 'repair'], { malformedMarkers: 'repair' }],
  '--clean': [['--clean', 'keep'], { clean: 'keep' }],
  '--changed': [['--changed', 'delete'], { changed: 'delete' }],
  '--export-dir': [['--export-dir', 'out'], { exportDir: 'out' }],
  '--no-color': [['--no-color'], { noColor: true }],
  '--static': [['--static'], { static: true }],
  '--narrow': [['--narrow'], { narrow: true }],
  '-y': [['-y'], { yes: true }],
  '--yes': [['--yes'], { yes: true }],
};

function helpFlags() {
  const help = buildHelpText(getCatalog(findPackageRoot()));
  const options = help.slice(help.indexOf('Options:'), help.indexOf('Run without a command'));
  return [...new Set(options.match(/(?<![\w-])--?[a-z][a-z-]*/g))];
}

test('parser: every flag printed by --help has a parser case', () => {
  const flags = helpFlags();
  assert.ok(flags.length > 20);
  assert.deepEqual(flags.filter((flag) => !FLAG_CASES[flag]), []);
});

for (const [flag, [args, expected]] of Object.entries(FLAG_CASES)) {
  test(`parser: ${flag} sets its field`, () => {
    const parsed = parseCliArgs(args);
    assert.deepEqual(parsed.unknown, []);
    for (const [key, value] of Object.entries(expected)) {
      assert.deepEqual(parsed[key], value, `${flag} -> ${key}`);
    }
  });
}

test('parser: hidden aliases keep working', () => {
  assert.equal(parseCliArgs(['-g']).global, true);
  assert.equal(parseCliArgs(['--cwd', 'app']).projectRoot, 'app');
  assert.equal(parseCliArgs(['--cwd=app']).projectRoot, 'app');
  assert.equal(parseCliArgs(['--list']).command, 'list');
  assert.equal(parseCliArgs(['check']).command, 'check');
  assert.equal(parseCliArgs(['add', 'sigmawrite']).command, 'add');
  assert.equal(parseCliArgs(['--link', '--copy']).method, 'conflict');
  assert.equal(parseCliArgs(['--confirm-purge=']).confirmPurge, '');
});

test('parser: install takes several positional skill ids and --skill values', () => {
  const parsed = parseCliArgs(['install', 'sigmawrite', 'sigmareview', '--skill', 'sigmabrief', '--yes']);
  assert.equal(parsed.command, 'install');
  assert.deepEqual(parsed.skillIds, ['sigmawrite', 'sigmareview', 'sigmabrief']);
  assert.deepEqual(parsed.unknown, []);
  assert.equal(parsed.yes, true);
});

test('parser: a value flag with a missing or dash-prefixed value fails with the flag name', () => {
  const cases = [
    [['uninstall', '--skill', '--yes'], /--skill requires a value/],
    [['install', 'sigmawrite', '--adopt-changed'], /--adopt-changed requires a value/],
    [['--project'], /--project requires a value/],
    [['--destination', '-y'], /--destination requires a value/],
    [['--skill='], /--skill requires a value/],
    [['--clean', 'maybe'], /--clean must be remove or keep/],
    [['--malformed-markers=nope'], /--malformed-markers must be skip, repair, or replace/],
    [['--adopt-legacy', 'nope'], /--adopt-legacy must be replace, skip, or export/],
    [['--changed', 'nope'], /--changed must be backup, keep, export, or delete/],
    [['--outside-edit', 'nope'], /--outside-edit must be replace, skip, or export/],
  ];
  for (const [args, message] of cases) {
    assert.throws(() => parseCliArgs(args), message, args.join(' '));
  }
});

test('parser: unknown flags and stray positionals are reported, not swallowed', () => {
  assert.deepEqual(parseCliArgs(['--unknown-flag']).unknown, ['--unknown-flag']);
  assert.deepEqual(parseCliArgs(['status', 'extra']).unknown, ['extra']);
});
