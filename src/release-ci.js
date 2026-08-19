import { runTrustedPublish, runTrustedValidate } from './release.js';

const mode = process.argv[2];

try {
  if (mode === 'validate') await runTrustedValidate(process.env);
  else if (mode === 'publish') await runTrustedPublish(process.env);
  else throw new Error('usage: node src/release-ci.js validate|publish');
} catch (err) {
  console.error(err.message || err);
  process.exit(1);
}
