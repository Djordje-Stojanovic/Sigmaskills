export const RELEASE_SCHEMA_VERSION = 1;
export const RELEASE_WORKFLOW_FILE = 'release.yml';
export const RELEASE_ENVIRONMENT = 'release';
export const RELEASE_DIST_TAG = 'latest';
export const RELEASE_PACKAGE_NAME = '@djordje-stojanovic/sigmaskills';
export const CHECKOUT_ACTION_PIN = '3d3c42e5aac5ba805825da76410c181273ba90b1';
export const SETUP_NODE_ACTION_PIN = '820762786026740c76f36085b0efc47a31fe5020';

export const TRUSTED_PUBLISHER_SETUP =
  'Configure an npm trusted publisher for this GitHub repository, workflow filename `release.yml`, and environment `release`. Publication cannot start until that one-time setup exists.';

export function inspectReleaseWorkflow(yaml) {
  const text = String(yaml || '');
  const errors = [];
  const onBlock = text.match(/\non:\s*\n([\s\S]*?)(?=\n(?:permissions|concurrency|env|jobs):|\njobs:)/);
  const onText = onBlock ? onBlock[1] : '';
  const triggers = [];
  if (/^\s{2}workflow_dispatch:/m.test(onText) || /^\s+workflow_dispatch:/m.test(text)) triggers.push('workflow_dispatch');
  if (/^\s{2}push:/m.test(onText)) {
    errors.push('release workflow must not publish on push');
    triggers.push('push');
  }
  if (/^\s{2}pull_request:/m.test(onText)) {
    errors.push('release workflow must not publish on pull_request');
    triggers.push('pull_request');
  }
  if (!triggers.includes('workflow_dispatch')) errors.push('release workflow must use workflow_dispatch');

  const usesFloatingTags = /uses:\s+actions\/(?:checkout|setup-node)@v\d+/m.test(text);
  if (usesFloatingTags) errors.push('release workflow must pin actions by commit SHA');

  const checkoutPin = (text.match(/uses:\s+actions\/checkout@([a-f0-9]{40})/) || [])[1] || null;
  const setupNodePin = (text.match(/uses:\s+actions\/setup-node@([a-f0-9]{40})/) || [])[1] || null;
  if (checkoutPin !== CHECKOUT_ACTION_PIN) errors.push('actions/checkout pin is missing or drifted');
  if (setupNodePin !== SETUP_NODE_ACTION_PIN) errors.push('actions/setup-node pin is missing or drifted');

  const parsePerms = (block) => {
    const perms = {};
    for (const line of String(block || '').split(/\n/)) {
      const match = line.match(/^\s+([a-z-]+):\s+(\w+)\s*$/);
      if (match) perms[match[1]] = match[2];
    }
    return perms;
  };
  const jobPermissions = (job) => {
    const match = text.match(new RegExp(`${job}:[\\s\\S]*?permissions:\\s*\\n((?:\\s{6,}[^\\n]+\\n)+)`));
    return parsePerms(match ? match[1] : '');
  };
  const environmentMatch = text.match(/publish:[\s\S]*?environment:\s+(\S+)/);
  const validate = { permissions: jobPermissions('validate') };
  const publish = {
    permissions: jobPermissions('publish'),
    environment: environmentMatch ? environmentMatch[1] : null,
  };

  if (validate.permissions.contents !== 'read') errors.push('validate job must use contents: read');
  if (validate.permissions['id-token']) errors.push('validate job must not receive id-token');
  if (publish.permissions['id-token'] !== 'write') errors.push('publish job must use id-token: write');
  if (publish.permissions.contents !== 'write') errors.push('publish job must use contents: write');
  if (publish.environment !== RELEASE_ENVIRONMENT) errors.push(`publish job must use environment ${RELEASE_ENVIRONMENT}`);
  if (!/node \.\/scripts\/release-ci\.js validate/.test(text)) errors.push('validate job must rebuild through release-ci.js');
  if (!/node \.\/scripts\/release-ci\.js publish/.test(text)) errors.push('publish job must publish through release-ci.js');

  return {
    ok: errors.length === 0,
    errors,
    triggers: [...new Set(triggers)],
    validate,
    publish,
    checkoutPin,
    setupNodePin,
    usesFloatingTags,
    trustedPublisherShape: publish.permissions['id-token'] === 'write' && publish.environment === RELEASE_ENVIRONMENT,
  };
}

function releasePointsAtCommit(githubRelease, gitTag, expected) {
  if (!githubRelease) return false;
  const tagged = gitTag && gitTag.commit === expected.commit;
  return githubRelease.targetCommit === expected.commit || tagged;
}

// Each check returns an error message, or null when the existing state is compatible.
function tagConflict({ expected, gitTag }) {
  if (gitTag && gitTag.commit && gitTag.commit !== expected.commit) {
    return `git tag v${expected.version} already points at ${gitTag.commit}; refusing to overwrite.`;
  }
  return null;
}

function releaseConflict({ expected, githubRelease, gitTag }) {
  if (githubRelease && githubRelease.targetCommit && githubRelease.targetCommit !== expected.commit && !releasePointsAtCommit(githubRelease, gitTag, expected)) {
    return `GitHub Release v${expected.version} already targets ${githubRelease.targetCommit}; refusing to duplicate or overwrite.`;
  }
  return null;
}

function npmConflict({ expected, npmPackage }) {
  const published = npmPackage?.versions?.[expected.version];
  if (published && published.integrity && expected.integrity && published.integrity !== expected.integrity) {
    return `npm already has ${RELEASE_PACKAGE_NAME}@${expected.version} with a different digest; versions are immutable.`;
  }
  return null;
}

export function evaluatePublicationGate({
  expected,
  workflow,
  npmPackage,
  githubRelease,
  gitTag,
  environment,
  trustedPublisher,
}) {
  const errors = [];
  if (workflow && workflow.ok === false) errors.push(...(workflow.errors || ['release workflow failed inspection']));
  if (!npmPackage?.exists) {
    errors.push(
      'Reserve the npm name `sigmaskills` at https://www.npmjs.com/package/sigmaskills, then configure a trusted publisher for workflow `release.yml` and GitHub Environment `release`.',
    );
  }
  if (trustedPublisher === false) errors.push(TRUSTED_PUBLISHER_SETUP);
  if (!environment || environment.name !== RELEASE_ENVIRONMENT) {
    errors.push('Create a GitHub Environment named `release` with required reviewers, then retry publication.');
  } else if (!environment.protected) {
    errors.push('Add protection rules (required reviewers) to the GitHub Environment named `release`.');
  }
  const ctx = { expected, npmPackage, githubRelease, gitTag };
  errors.push(...[tagConflict(ctx), releaseConflict(ctx), npmConflict(ctx)].filter(Boolean));
  return { ok: errors.length === 0, errors };
}

// The setup gate and the recovery plan for the same published state.
export function evaluatePublication({ expected, workflow, npmPackage, githubRelease, gitTag, environment, trustedPublisher }) {
  return {
    gate: evaluatePublicationGate({ expected, workflow, npmPackage, githubRelease, gitTag, environment, trustedPublisher }),
    recovery: planIdempotentPublish({ expected, npmPackage, githubRelease, gitTag }),
  };
}

export function planIdempotentPublish({ expected, npmPackage, githubRelease, gitTag }) {
  const ctx = { expected, npmPackage, githubRelease, gitTag };
  const errors = [npmConflict(ctx), tagConflict(ctx), releaseConflict(ctx)].filter(Boolean);
  if (errors.length) return { ok: false, errors, publishNpm: false, createGithubRelease: false, createTag: false };
  const published = npmPackage?.versions?.[expected.version];
  const sameNpm = Boolean(published && (!expected.integrity || published.integrity === expected.integrity));
  const sameRelease = releasePointsAtCommit(githubRelease, gitTag, expected);
  const sameTag = Boolean(gitTag && gitTag.commit === expected.commit);
  return {
    ok: true,
    errors,
    publishNpm: !sameNpm,
    createGithubRelease: !sameRelease,
    createTag: !sameTag,
  };
}
