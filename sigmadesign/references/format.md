# The DESIGN.md format

SigmaDesign writes and reads the Google Stitch `DESIGN.md` format (`version: alpha`): YAML front matter of tokens, then prose. Anything that reads that format (the `@google/design.md` linter, other agents) reads these files.

## Front matter

```yaml
---
version: alpha
name: Harbour-Ledger
description: one sentence on the look
colors:
  canvas: "#0a0b0d"          # dark is the default; every key without a prefix is dark
  surface: "#111315"
  primary: "#e8a33d"
  on-primary: "#241706"
  light-canvas: "#f9fafb"    # the light theme: same names with a light- prefix
typography:
  heading-lg: { ... }        # fontFamily, fontSize, fontWeight, lineHeight, letterSpacing
rounded: { sm: 6px, md: 10px, lg: 14px, full: 9999px }
spacing: { sm: 8px, lg: 16px, section: 64px }
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.md}"
---
```

The helper reads a small YAML subset: nested maps and scalars, one per line. No lists, no multi-line values, no anchors. Write tokens that way and the helper and the linter both accept them.

## Colour roles

| Role | Tokens | Rule |
|---|---|---|
| Ground | `canvas`, `glow` | The page. `glow` is a faint accent-tinted light behind the top corner (equal to `canvas` in light). |
| Surfaces | `surface`, `surface-2`, `surface-3` | Each step one notch lighter (darker in light). Cards sit on `surface`. |
| Lines | `hairline`, `hairline-strong` | 1 px borders. No card shadows. |
| Text | `ink`, `body`, `mute` | `ink` headings, `body` paragraphs, `mute` the quietest text that passes 4.5:1 on `surface-2`. |
| Accent | `primary`, `primary-hover`, `primary-deep`, `on-primary` | The one accent. `on-primary` is the text on it. |
| State | `ok`, `warn`, `err`, `info` | Only for state, never for decoration. |

## Packs

`design.packs.json` next to `DESIGN.md`:

```json
{ "yellow-black": { "mode": "dark", "accent": "#fbbf24", "colors": { "canvas": "#...", "primary": "#..." } } }
```

Do not edit the colours by hand; run `pack` again with another accent (it replaces the entry). A pack has the same token names as the base so any page works in any pack.

## Generated files

| File | From | Use |
|---|---|---|
| `tokens.css` | colours, `rounded`, `spacing`, type families and sizes | `:root` (dark), `:root[data-theme="light"]`, one block per pack |
| `tailwind.css` | the dark colour names | `@theme inline` map so `bg-surface`, `text-ink` work in Tailwind 4 |
| `components.css` | fixed | shell, card, buttons, chip, field, swatches; tokens only |
| `index.html` | everything | the sample page and theme switch |
