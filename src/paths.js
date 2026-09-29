import path from 'node:path';

/**
 * Whether a path is the base folder or lives under it. Names that only start with two dots
 * (such as `..cache`) count as inside.
 *
 * @param {string} base
 * @param {string} target
 * @returns {boolean}
 */
export function isPathInside(base, target) {
  const relative = path.relative(path.resolve(base), path.resolve(target));
  return !(relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative));
}

/**
 * Reject a recorded path that leaves its base folder. State, journals, and backup metadata sit on
 * disk where anyone can edit them, so no recorded path may reach outside the project, home, or state dir.
 *
 * @param {string} base
 * @param {string} recorded
 * @param {string} what
 */
export function assertPathInside(base, recorded, what) {
  if (!isPathInside(base, path.resolve(base, recorded))) {
    throw new Error(`${what} '${recorded}' escapes ${base}`);
  }
}
