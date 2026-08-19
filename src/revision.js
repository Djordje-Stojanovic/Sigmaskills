import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

/**
 * Recursively list all files in a directory, returning paths relative to rootDir
 * with POSIX forward slashes.
 *
 * @param {string} dir
 * @param {string} [baseDir]
 * @returns {string[]}
 */
export function listRelativeFiles(dir, baseDir = dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const results = [];

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...listRelativeFiles(fullPath, baseDir));
    } else if (entry.isFile()) {
      const relPath = path.relative(baseDir, fullPath).replace(/\\/g, '/');
      results.push(relPath);
    }
  }

  return results;
}

/**
 * Compute deterministic SHA-256 revision hash and per-file hashes for a skill directory
 * in a single disk pass.
 *
 * @param {string} skillDir
 * @returns {{ revision: string, files: Record<string, string> }}
 */
export function computeSkillRevisionAndHashes(skillDir) {
  const relFiles = listRelativeFiles(skillDir);
  relFiles.sort();

  const folderHash = crypto.createHash('sha256');
  const files = {};

  for (const relPath of relFiles) {
    const fullPath = path.join(skillDir, relPath);
    const fileBytes = fs.readFileSync(fullPath);

    // Update combined folder hash
    folderHash.update(relPath);
    folderHash.update('\0');
    folderHash.update(fileBytes);
    folderHash.update('\0');

    // Record per-file hash
    files[relPath] = crypto.createHash('sha256').update(fileBytes).digest('hex');
  }

  return {
    revision: folderHash.digest('hex'),
    files,
  };
}

/**
 * Compute deterministic SHA-256 revision hash for a skill directory.
 *
 * @param {string} skillDir
 * @returns {string} SHA-256 hex string (64 characters)
 */
export function computeSkillRevision(skillDir) {
  return computeSkillRevisionAndHashes(skillDir).revision;
}

/**
 * Compute SHA-256 hash for every file in a skill directory.
 *
 * @param {string} skillDir
 * @returns {Record<string, string>}
 */
export function computeFileHashes(skillDir) {
  return computeSkillRevisionAndHashes(skillDir).files;
}
