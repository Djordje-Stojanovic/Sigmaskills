---
name: sigmadesign
description: Build a repo's design system from one accent colour (DESIGN.md tokens). Use when the user wants a design system, template, theme or one design file. Do not use to critique a look (SigmaTaste).
---

# SigmaDesign

Turn a brief into a design system that lives in one file, `DESIGN.md`, and make every page and repo follow it. One accent colour in, a checked palette out: dark and light, any number of colour packs, type, spacing, corners, components and a sample page that proves it. The bar: a new page built from the tokens looks like the same product, a new colour pack is one command, and nobody writes a colour twice.

## Operating contract

- **One source.** `DESIGN.md` (YAML tokens on top, prose below) is the truth. Generated files (`tokens.css`, `tailwind.css`, `components.css`) are never edited by hand: change `DESIGN.md` or `design.packs.json`, run `build` again. Format: [format.md](references/format.md).
- **The repo's own look wins.** When the repo already has a `DESIGN.md`, brand file or theme, use Apply (step 4); never start a second system next to it. Leaving a chosen brand is a finding, not a freedom.
- **Tokens only in pages.** Page CSS reads `var(--token)`. A colour literal in a page is a bug the `scan` command finds.
- **Contrast is measured.** Text pairs reach 4.5:1 and the accent against its ground 3:1 in dark, light and every pack. `check` fails below that and tells you the pair. A failing accent is darkened or lightened by the tool; say so to the owner.
- **Looking is the test.** Done means you looked at the sample page and the real page at 1440 and 375 px in every theme: [quality.md](references/quality.md).
- **No overwrite.** `new` refuses a folder that already has a `DESIGN.md`. `integrate` and `scan` write only with `--write`.
- **Shell native to the machine:** PowerShell on Windows, POSIX shell elsewhere. Close any server you start before you stop.

The helper is one standard-library Python file: `python scripts/sigmadesign.py -h`. Run `selftest` once if you doubt it works here.

## 1. Look, then ask once

Read what exists: `DESIGN.md`, brand files, theme or token files, the CSS entry, the font in use, a live URL if one is named. Then ask one numbered round, at most 6 questions, each with `Recommended:` and a few words of why; use `/grilling`'s format when installed. Skip what the owner already said, and log each answer you took for him as `Ruling:`.

1. What is it for, who uses it, and which mode: Persuade (landing page), Read (docs), Operate (dashboard, tool)?
2. The accent colour (a hex, a brand, or "pick one" with your pick and why), and the neutral tint: cool, warm, or the accent's own hue.
3. Dark or light as the default, and whether the other is offered.
4. Type: one family or two, and where it loads from (self-host the file; do not link a CDN you cannot guarantee).
5. Corners: sharp, soft or round.
6. Where it goes: a new site, one existing site, or every repo.

## 2. Create

Use `/frontend-design` for the point of view: choose one memorable thing and keep the rest quiet; avoid the spent defaults (identical rounded cards, a gradient wash, the all-caps eyebrow on every heading).

1. `python scripts/sigmadesign.py new <dir> --name "<Name>" --accent "#hex" [--neutral-hue DEG --neutral-sat PCT --font "<Family>" --corners soft]` writes `<dir>/DESIGN.md`.
2. Replace every `FILL` marker in the prose (Overview, Typography, Layout, Components, Responsive Behavior) with decisions for this product. A line the product does not need is deleted, not left empty.
3. Add the components the product needs under `components:` using only token references (`"{colors.primary}"`).
4. `python scripts/sigmadesign.py build <dir>/DESIGN.md --out <dir>/site`, then `check <dir>/DESIGN.md --out <dir>/site`. Exit 0.
5. When the network is available, `npx @google/design.md lint <dir>/DESIGN.md` must report 0 errors.
6. Open `<dir>/site/index.html` and look (step 6).

Done when: `DESIGN.md` has no `FILL`, `check` exits 0 and the sample page was looked at.

## 3. Colour packs

`python scripts/sigmadesign.py pack <DESIGN.md> --name yellow-black --accent "#fbbf24"` adds a full palette, `--light` makes a light one. Packs sit in `design.packs.json` beside `DESIGN.md`; `build` emits `[data-theme="yellow-black"]` blocks, and the sample page gets a switch chip for each. Name a pack as `<accent>-<ground>`. A pack never changes type, spacing or corners: only colour. The tool pushes the accent until contrast passes, so a pale yellow becomes a readable one on white.

## 4. Apply to a page or app

1. Link `tokens.css` then `components.css` once (Tailwind 4 projects import `tailwind.css` too; React and Vite import the same files).
2. Build from the parts: `.wrap`, `.topbar`, `.hero`, `.grid`, `.card`, `.btn` (`btn-primary`, `btn-ghost`), `.chip`, `.field` and `.input`, `.label`. Copy the sample page's structure; add a component to `DESIGN.md` first, then to the generated set only if every page needs it.
3. One filled primary button per view. Labels use `.label`. Headings keep the weight in `typography`.
4. Theme switch: set `data-theme` on `<html>`; keep the visitor's choice in `localStorage` inside try and catch.

## 5. Integrate across a repo

Follow [integrate.md](references/integrate.md). In short: `scan <repo> --tokens DESIGN.md` lists every hard-coded colour with its nearest token; `scan --write` rewrites exact matches in `.css` and `.scss` to `var(--token)`; the rest you map by hand and say why. `integrate <DESIGN.md> <repo> --write` puts `DESIGN.md` at the repo root byte for byte and adds one pointer line to `AGENTS.md` and `CLAUDE.md`. Add `check` with `--out` to the repo's checks so a stale `tokens.css` fails.

Done when: `scan` shows no colour literal outside the tokens (or a named reason for each), every repo copy of `DESIGN.md` is identical, and the changed pages were looked at.

## 6. Look

Open the sample page and one real page at 1440 and 375 px in dark, light and each pack. Take screenshots. Fix what a stranger would notice first. The checklist: [quality.md](references/quality.md).

## Final response

1. The paths: `DESIGN.md`, the build folder, the screenshots.
2. The palette in one line (accent, ground, packs) and any accent the tool had to adjust.
3. The `check` result and the lint result.
4. Per repo: what moved, what was left, and why.
5. Next command the owner can run (a new pack, a rebuild).

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
