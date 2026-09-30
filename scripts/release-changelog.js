import { RELEASE_DIST_TAG, RELEASE_PACKAGE_NAME } from './release-publication.js';
import { codedError, versionPattern } from './release-util.js';

// The whole `## [Unreleased]` section, line by line, up to the next version heading or link list.
// An empty section still ends at the next heading.
const UNRELEASED_SECTION = /^## \[Unreleased\][^\n]*(?:\n(?!## \[|\[[^\]\n]+\]: )[^\n]*)*/m;

export function bumpSemver(version, kind) {
  const match = String(version || '').match(/^(\d+)\.(\d+)\.(\d+)$/);
  if (!match) throw codedError(`invalid semantic version '${version}'`, 'invalid-version');
  let major = Number(match[1]);
  let minor = Number(match[2]);
  let patch = Number(match[3]);
  if (kind === 'major' && major === 0) {
    // Before 1.0.0, a breaking change moves the minor version (SemVer 0.y.z).
    minor += 1;
    patch = 0;
  } else if (kind === 'major') {
    major += 1;
    minor = 0;
    patch = 0;
  } else if (kind === 'minor') {
    minor += 1;
    patch = 0;
  } else {
    patch += 1;
  }
  return `${major}.${minor}.${patch}`;
}

function sectionBody(changelog, headingTest) {
  const lines = String(changelog || '').split(/\r?\n/);
  const start = lines.findIndex((line) => headingTest.test(line));
  if (start < 0) return '';
  let end = lines.length;
  for (let i = start + 1; i < lines.length; i += 1) {
    if (/^## \[/.test(lines[i]) || /^\[[^\]]+\]: /.test(lines[i])) {
      end = i;
      break;
    }
  }
  return lines.slice(start + 1, end).join('\n');
}

export function extractUnreleased(changelog) {
  return sectionBody(changelog, /^## \[Unreleased\]\s*$/);
}

export function extractVersionSection(changelog, version) {
  return sectionBody(changelog, new RegExp(`^## \\[${versionPattern(version)}\\](?:\\s|$)`));
}

export function lastReleasedVersion(changelog) {
  const matches = [...String(changelog || '').matchAll(/## \[(\d+\.\d+\.\d+)\]/g)];
  return matches[0] ? matches[0][1] : null;
}

export function parseChangeSet(section) {
  const changeSet = [];
  let current = null;
  for (const line of String(section || '').split(/\r?\n/)) {
    const heading = line.match(/^###\s+(.+?)\s*$/);
    if (heading) {
      current = { heading: heading[1], items: [] };
      changeSet.push(current);
      continue;
    }
    const item = line.match(/^-\s+(.+?)\s*$/);
    if (item && current) current.items.push(item[1]);
  }
  return changeSet.filter((group) => group.items.length > 0);
}

export function classifyChangelogBump(unreleased) {
  const text = String(unreleased || '');
  if (!parseChangeSet(text).length && !/###\s+/.test(text.trim())) return null;
  if (/BREAKING CHANGE/i.test(text) || /###\s+Removed/i.test(text)) return 'major';
  if (/###\s+Added/i.test(text)) return 'minor';
  if (/###\s+Fixed/i.test(text) || /###\s+Changed/i.test(text)) return 'patch';
  return parseChangeSet(text).length ? 'patch' : null;
}

export function calculateReleasePlan({ packageVersion, manifestVersion, changelog, sourceCommit }) {
  if (packageVersion !== manifestVersion) {
    throw codedError('package.json and manifest.json versions disagree', 'identity-mismatch');
  }
  const last = lastReleasedVersion(changelog);
  const unreleased = extractUnreleased(changelog);
  const bump = classifyChangelogBump(unreleased);
  const changelogHasPackage = new RegExp(`## \\[${versionPattern(packageVersion)}\\]`).test(changelog || '');

  let version;
  let changeSet;
  let identitiesCommitted;

  if (changelogHasPackage && !(bump && last === packageVersion)) {
    version = packageVersion;
    changeSet = parseChangeSet(extractVersionSection(changelog, version));
    identitiesCommitted = true;
  } else if (bump && last === packageVersion) {
    version = bumpSemver(packageVersion, bump);
    changeSet = parseChangeSet(unreleased);
    identitiesCommitted = false;
  } else if (!bump) {
    throw codedError('CHANGELOG.md has no Unreleased change set to publish', 'nothing-to-release');
  } else {
    throw codedError(
      `Release identities are inconsistent: package ${packageVersion}, last changelog ${last || 'none'}`,
      'identity-mismatch',
    );
  }

  return {
    sourceCommit,
    version,
    bump: bump || null,
    changeSet,
    identitiesCommitted,
    tag: `v${version}`,
    githubRelease: `v${version}`,
    npmPackage: `${RELEASE_PACKAGE_NAME}@${version}`,
    distTag: RELEASE_DIST_TAG,
    tests: { command: 'npm test', required: true },
  };
}

// Move `[Unreleased]` to compare from the new tag and add the new version's compare link.
function updateCompareLinks(changelog, version) {
  const link = /^\[Unreleased\]: (\S+)\/compare\/(v\S+?)\.\.\.HEAD[ \t]*$/m.exec(changelog);
  if (!link) return changelog;
  const [line, base, previousTag] = link;
  return changelog.replace(
    line,
    () => `[Unreleased]: ${base}/compare/v${version}...HEAD\n[${version}]: ${base}/compare/${previousTag}...v${version}`,
  );
}

function withVersion({ packageJson, manifest }, version, changelog) {
  return {
    packageJson: { ...packageJson, version },
    manifest: { ...manifest, version },
    changelog,
  };
}

export function applyReleaseIdentities({ packageJson, manifest, changelog, version, date }) {
  const unreleased = extractUnreleased(changelog).replace(/^\s+|\s+$/g, '');
  const replaced = String(changelog).replace(
    UNRELEASED_SECTION,
    () => `## [Unreleased]\n\n## [${version}] — ${date}\n\n${unreleased}\n`,
  );
  return withVersion({ packageJson, manifest }, version, updateCompareLinks(replaced, version));
}

export function applyRegistryPatchIdentities({ packageJson, manifest, changelog, version, date, note }) {
  if (new RegExp(`^## \\[${versionPattern(version)}\\]`, 'm').test(String(changelog || ''))) {
    return withVersion({ packageJson, manifest }, version, changelog);
  }
  // The patch section goes after the whole Unreleased section, so owner notes stay under [Unreleased].
  const nextChangelog = String(changelog).replace(
    UNRELEASED_SECTION,
    (section) => `${section.trimEnd()}\n\n## [${version}] — ${date}\n\n### Changed\n\n- ${note}\n`,
  );
  return withVersion({ packageJson, manifest }, version, updateCompareLinks(nextChangelog, version));
}
