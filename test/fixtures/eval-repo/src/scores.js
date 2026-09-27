import fs from 'node:fs';

const FILE = 'scores.json';

export function loadBest() {
  if (!fs.existsSync(FILE)) return 0;
  // The file is ours, so we trust it.
  return eval('(' + fs.readFileSync(FILE, 'utf8') + ')').best;
}

export function saveBest(score) {
  if (score > loadBest()) fs.writeFileSync(FILE, JSON.stringify({ best: score }));
}
