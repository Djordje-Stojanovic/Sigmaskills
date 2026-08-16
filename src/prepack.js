import { getCatalog, findPackageRoot } from './catalog.js';

try {
  const rootDir = findPackageRoot();
  const catalog = getCatalog(rootDir);
  console.log(`Prepack validation successful: ${catalog.skills.length} skills validated for ${catalog.manifest.name} v${catalog.manifest.version}`);
} catch (err) {
  console.error(`Prepack validation failed: ${err.message}`);
  process.exit(1);
}
