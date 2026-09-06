# SigmaRefactor scan rules

Use this reference for the first step of SigmaRefactor. Keep the scan reproducible.

## Preferred command

On Thinkcenter_Setup, `laloc` counts physical lines in maintained code and text files. It accepts `-p <path>`, `-m <minimum>`, and repeated `-x <glob>` exclusions. Run it as:

```powershell
laloc -p <root> -m 0 -x '*.md','*.mdx','*.txt','*.rst','*.adoc','*.lock'
```

Use the repository root as `<root>`. The command reports buckets and a total. `-m 0` lists every counted file. It does not provide an include-extension filter.

## Reconciliation

Build a second inventory with Git or the native file API. Include maintained source, tests, scripts, and configuration. Exclude generated output, dependency trees, binary files, prose, and lockfiles. Compare the inventory with the `laloc` paths.

The current Thinkcenter_Setup implementation skips names such as `bin`, `packages`, `node_modules`, `dist`, `build`, `.git`, `.scratch`, `tmp`, and `temp`. Some repositories maintain source in those folders. Report every eligible omitted file and count it with the fallback method before ranking.

Rank by physical line count. Break equal counts by the normalized repository path in ascending order. A file with fewer than five eligible files is still a valid result.

## Fallback

If `laloc` is missing, fails, or cannot read a file, say so. Use Git's tracked file list where available, then count lines with a native command or API. Do not install tools, source a complete machine profile, or silently change the exclusions.

## Evidence

Keep the scan output, inventory, excluded paths, unreadable paths, and final ranking in the conversation or the agreed report. Do not claim that a file was read when only a truncated preview was available.
