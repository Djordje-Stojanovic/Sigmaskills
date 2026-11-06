// A node --test reporter that writes the serial seconds of each test file to the path in SIGMA_TEST_TIMING,
// so scripts/run-tests.js can name the slowest files when the run goes over its budget.
import { writeFileSync } from 'node:fs';

export default async function* timing(source) {
  const seconds = {};
  for await (const event of source) {
    if ((event.type === 'test:pass' || event.type === 'test:fail') && event.data.nesting === 0 && event.data.file) {
      seconds[event.data.file] = (seconds[event.data.file] || 0) + (event.data.details?.duration_ms || 0) / 1000;
    }
  }
  if (process.env.SIGMA_TEST_TIMING) writeFileSync(process.env.SIGMA_TEST_TIMING, JSON.stringify(seconds));
}
