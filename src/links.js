import fs from 'node:fs';
import path from 'node:path';

/**
 * Recommended on-disk link method for this operating system.
 *
 * @returns {'junction' | 'symlink'}
 */
export function recommendedLinkMethod() {
  return process.platform === 'win32' ? 'junction' : 'symlink';
}

/**
 * Whether a path exists without following a symbolic link or junction.
 *
 * @param {string} destPath
 * @returns {boolean}
 */
export function pathExists(destPath) {
  try {
    fs.lstatSync(destPath);
    return true;
  } catch (err) {
    if (err.code === 'ENOENT' || err.code === 'ENOTDIR') return false;
    throw err;
  }
}

function isInsideProject(projectRoot, absolutePath) {
  const relative = path.relative(path.resolve(projectRoot), path.resolve(absolutePath));
  return relative === '' || (relative && !relative.startsWith('..') && !path.isAbsolute(relative));
}

/**
 * Remove a managed destination without following a link into its target.
 *
 * @param {string} destPath
 */
export function removeManagedPath(destPath) {
  if (!pathExists(destPath)) return;
  const stat = fs.lstatSync(destPath);
  if (stat.isSymbolicLink()) {
    fs.unlinkSync(destPath);
    return;
  }
  fs.rmSync(destPath, { recursive: true, force: true });
}

/**
 * Inspect a managed destination without following it.
 *
 * @param {string} destPath
 * @param {string} [expectedTarget]
 * @returns {object}
 */
export function inspectManagedPath(destPath, expectedTarget) {
  if (!pathExists(destPath)) {
    return { method: null, broken: false, wrongTarget: false, missing: true };
  }

  const stat = fs.lstatSync(destPath);
  if (!stat.isSymbolicLink()) {
    return { method: 'copy', broken: false, wrongTarget: false, missing: false };
  }

  const method = recommendedLinkMethod();
  let rawTarget;
  try {
    rawTarget = fs.readlinkSync(destPath);
  } catch {
    return { method, broken: true, wrongTarget: false, missing: false };
  }

  const resolvedTarget = path.resolve(path.dirname(destPath), rawTarget);
  let realPath = null;
  let broken = false;
  try {
    realPath = fs.realpathSync(destPath);
    if (!pathExists(resolvedTarget) && !fs.existsSync(resolvedTarget)) broken = true;
  } catch {
    broken = true;
  }

  let wrongTarget = false;
  if (expectedTarget) {
    if (realPath) {
      try {
        wrongTarget = realPath !== fs.realpathSync(expectedTarget);
      } catch {
        wrongTarget = true;
      }
    } else {
      wrongTarget = path.resolve(resolvedTarget) !== path.resolve(expectedTarget);
    }
  }

  return { method, broken, wrongTarget, missing: false, target: resolvedTarget };
}

/**
 * Create a directory junction on Windows or a symbolic link elsewhere.
 *
 * @param {string} linkPath
 * @param {string} targetPath
 * @param {string} [projectRoot]
 * @returns {{ method: 'junction' | 'symlink', linkPath: string, targetPath: string }}
 */
export function createSkillLink(linkPath, targetPath, projectRoot) {
  const resolvedLink = path.resolve(linkPath);
  const resolvedTarget = path.resolve(targetPath);
  const method = recommendedLinkMethod();

  if (projectRoot) {
    if (!isInsideProject(projectRoot, resolvedLink)) {
      throw new Error(`link destination '${resolvedLink}' escapes the project`);
    }
    if (!isInsideProject(projectRoot, resolvedTarget)) {
      throw new Error(`link target '${resolvedTarget}' escapes the project`);
    }
  }

  if (!fs.existsSync(resolvedTarget)) {
    throw new Error(`link target '${resolvedTarget}' does not exist`);
  }

  if (pathExists(resolvedLink)) {
    throw new Error(`link destination '${resolvedLink}' already exists`);
  }

  const parent = path.dirname(resolvedLink);
  if (!fs.existsSync(parent)) {
    fs.mkdirSync(parent, { recursive: true });
  }

  const type = method === 'junction' ? 'junction' : 'dir';
  const symlinkTarget = method === 'junction'
    ? resolvedTarget
    : (path.relative(parent, resolvedTarget) || '.');

  try {
    fs.symlinkSync(symlinkTarget, resolvedLink, type);
  } catch (err) {
    const wrapped = new Error(`failed to create ${method} at '${resolvedLink}': ${err.message}`);
    wrapped.cause = err;
    wrapped.code = err.code;
    wrapped.linkMethod = method;
    wrapped.linkPath = resolvedLink;
    wrapped.targetPath = resolvedTarget;
    throw wrapped;
  }

  return {
    method,
    linkPath: resolvedLink,
    targetPath: resolvedTarget,
  };
}
