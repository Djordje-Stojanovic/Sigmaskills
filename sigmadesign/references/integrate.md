# Integrate a design system across a repo

Run these in order for each repo. `<S>` is `scripts/sigmadesign.py`. Every writing command takes `--write`; without it the command only reports.

## 1. Look at the repo

Find where styles live: global CSS, Tailwind config or `@theme`, CSS modules, styled components, inline styles, design-token JSON, a theme file. Find the framework's font loading. Note the repo's line ending: if `DESIGN.md` is CRLF in the master, keep it byte for byte (copy the file, never retype it).

## 2. Scan

```
python <S> scan <repo> --tokens <DESIGN.md>
```

Each row: a colour literal, how many times it appears, and either `-> var(--token)` (exact match) or `nearest --token (#hex)`. The scan skips `node_modules`, `.git`, `dist`, `build`, vendored folders and the generated token files.

## 3. Move the exact matches

`scan --write` rewrites exact matches in `.css` and `.scss` files to `var(--token)`. Review the diff. For the rest:

- **Near a token** (a grey one step off): use the token; the small shift is the point of a system.
- **A brand colour of a third party** (a logo, a chart series defined elsewhere): keep it and write the reason as a comment.
- **In JS, JSX or TSX** (inline styles, chart libraries): read the token at run time, `getComputedStyle(document.documentElement).getPropertyValue('--primary')`, or use the Tailwind class.
- **A new tone the system lacks**: add a token to `DESIGN.md`, build again, then use it. Never add a literal.

## 4. Wire it

- Import `tokens.css` and `components.css` once at the entry. Tailwind 4: also `tailwind.css`.
- Map the old variable names the repo used (`--bg`, `--accent`) as aliases in one small `aliases.css` that points at the new tokens, so components move without edits.
- Self-host the font file named in `typography`; do not rely on a CDN.

## 5. Make the repo follow it

```
python <S> integrate <DESIGN.md> <repo> --write
```

This copies `DESIGN.md` to the repo root byte for byte and adds one pointer line to `AGENTS.md` and `CLAUDE.md` when they exist and do not already mention `DESIGN.md`. A repo with neither file gets the copy only; say so in the report.

Several repos share one master. Keep one master file (name it in the pointer) and add a test or check that every copy is byte-identical to it. Do not fork the file per repo; a change goes to the master, then to the copies.

## 6. Keep it from drifting

Add to the repo's checks: `python <S> check DESIGN.md --out <build dir>` (contrast and a stale `tokens.css`), and `python <S> scan . --tokens DESIGN.md` as a report. A rebuild is one command.

## 7. Report

Per repo: files changed, literals moved, literals left with the reason, screenshots before and after for the pages you touched.
