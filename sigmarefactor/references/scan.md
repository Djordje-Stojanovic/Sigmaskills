# SigmaRefactor scan rules

Use this reference for the first step of SigmaRefactor. Keep the scan reproducible.

## Preferred command

The PowerShell `laloc` implementation in Thinkcenter_Setup counts physical lines. It accepts `-p <path>`, `-m <minimum>`, and one `-x` string-array parameter. Run it as:

```powershell
laloc -p '<root>' -m 0 -x '*.md','*.mdx','*.rst','*.adoc','*.lock','package-lock.json','npm-shrinkwrap.json','pnpm-lock.yaml','yarn.lock'
```

Use the repository root as `<root>`. The command reports buckets and a total. `-m 0` lists every counted file. It does not provide an include-extension filter.

## Reconciliation

Build a second inventory with `git -C <root> ls-files --cached --others --exclude-standard -z`. Parse NUL separators and deduplicate paths. This includes maintained untracked files. Without Git, use a native inventory with the repository's ignore rules. Include maintained source, tests, scripts, and configuration. Exclude generated output, dependency trees, binary files, prose, and lockfiles. Show exclusions and their reasons. Inspect file purpose: `CMakeLists.txt` is configuration, and tracked files can still be generated. Compare the inventory with the `laloc` paths, removing ineligible results as well as adding omitted eligible files.

The current Thinkcenter_Setup implementation skips names such as `bin`, `packages`, `node_modules`, `dist`, `build`, `.git`, `.scratch`, `tmp`, and `temp`. Some repositories maintain source in those folders. Report every eligible omitted file and count it with the fallback method before ranking.

Rank by physical line count. Break equal counts by the normalized repository-relative path in ordinal ascending order. A repository with fewer than five eligible files is still a valid result.

## Fallback

If `laloc` is missing, fails, or cannot read a file, say so. Count the eligible inventory with a native command or API. Decode text using its actual encoding. An empty file has zero lines; count each physical line once, including a final unterminated line. CRLF is one separator. Do not install tools, source a complete machine profile, or silently change the exclusions.

On hosts with Node.js, this recipe ranks an already-reviewed eligible path list. Supply a reader that returns decoded text, such as `fs.readFileSync(path.join(root, relative), 'utf8')` for UTF-8 source. Eligibility filtering stays explicit.

```javascript
function rankFiles(eligiblePaths, readText) {
  const files = [];
  const unreadable = [];
  for (const relative of new Set(eligiblePaths)) {
    try {
      const text = readText(relative);
      const separators = text.match(/\r\n|\r|\n/g) || [];
      const lines = separators.length + (text.length > 0 && !/[\r\n]$/.test(text) ? 1 : 0);
      files.push({ path: relative.replaceAll('\\', '/'), lines });
    } catch (error) {
      unreadable.push({ path: relative, error: error.message });
    }
  }
  files.sort((a, b) => b.lines - a.lines || (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
  return { top: files.slice(0, 5), files, unreadable, complete: unreadable.length === 0 };
}
```

## Evidence

Keep the scan output, inventory, excluded paths, unreadable paths, and final ranking in the conversation or the agreed report. An unreadable eligible file makes the ranking incomplete; resolve that limit with the user before choosing a refactoring target. Do not claim that a file was read when only a truncated preview was available.
