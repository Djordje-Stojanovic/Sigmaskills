---
version: alpha
name: Black-Green
description: The one look of the SigmaSkills pages, the installer and the owner's sites (a homepage, an audio studio, a personal site with docs). A near-black zinc canvas with a faint green glow, one emerald accent, hairline borders, Inter, and one character picture from our own art library behind the page. The art carries the colour and the drama; the UI stays quiet, dense and fast. Built from what the four sites already share, with the best of Spotify (the art is the colour), Raycast (surface ladder, hairlines, command palette) and Supabase (one emerald, used scarce, dark ink on green).

colors:
  canvas: "#09090b"
  glow: "#0b2a20"
  surface: "#111113"
  surface-2: "#18181b"
  surface-3: "#1f1f23"
  hairline: "#27272a"
  hairline-strong: "#3f3f46"
  ink: "#f4f4f5"
  body: "#d4d4d8"
  mute: "#a1a1aa"
  primary: "#34d399"
  primary-hover: "#6ee7b7"
  primary-deep: "#10b981"
  on-primary: "#022c22"
  ok: "#6ee7b7"
  warn: "#fbbf24"
  err: "#f87171"
  info: "#7dd3fc"
  light-canvas: "#fafafa"
  light-surface: "#ffffff"
  light-surface-2: "#f4f4f5"
  light-hairline: "#e4e4e7"
  light-ink: "#18181b"
  light-mute: "#52525b"
  light-primary: "#047857"
  light-on-primary: "#ecfdf5"

typography:
  display:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: 48px
    fontWeight: 600
    lineHeight: 1.08
    letterSpacing: -0.025em
  heading-xl:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 28px
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: -0.015em
  heading-lg:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 22px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: -0.01em
  heading-md:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0
  body-lg:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 18px
    fontWeight: 400
    lineHeight: 1.65
    letterSpacing: 0.01em
  body-md:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.7
    letterSpacing: 0
  body-sm:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0
  button:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.0
    letterSpacing: 0
  caption:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0
  label:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 12px
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: 0.08em
  micro:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 10px
    fontWeight: 500
    lineHeight: 1.0
    letterSpacing: 0
  code:
    fontFamily: "ui-monospace, 'Cascadia Code', 'SF Mono', Menlo, Consolas, monospace"
    fontSize: 13.5px
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: 0

rounded:
  xs: 4px
  sm: 6px
  md: 10px
  lg: 14px
  xl: 16px
  full: 9999px

spacing:
  xxs: 2px
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  xxl: 32px
  section: 64px
  huge: 96px

components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 0px 16px
    height: 36px
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 0px 16px
    height: 36px
  button-outline:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 0px 16px
    height: 36px
  button-ghost:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.mute}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 0px 12px
    height: 36px
  button-danger:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.err}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 0px 16px
    height: 36px
  button-icon:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.body}"
    rounded: "{rounded.md}"
    size: 44px
  button-play:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.full}"
    size: 36px
  text-input:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 0px 12px
    height: 40px
  search-trigger:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.mute}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 0px 10px
    height: 44px
  command-palette:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.xl}"
    padding: 8px
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.lg}"
    padding: 16px
  tile:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.lg}"
    padding: 12px 16px
    height: 56px
  nav-item:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.mute}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 8px 10px
  nav-item-active:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 8px 10px
  callout-context:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.body}"
    typography: "{typography.body-md}"
    rounded: "{rounded.lg}"
    padding: 12px 16px
  callout-warn:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.body}"
    typography: "{typography.body-md}"
    rounded: "{rounded.lg}"
    padding: 14px 18px
  callout-tip:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.body}"
    typography: "{typography.body-md}"
    rounded: "{rounded.lg}"
    padding: 14px 18px
  chip:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.body}"
    typography: "{typography.caption}"
    rounded: "{rounded.full}"
    padding: 5px 11px
  badge:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.primary}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: 0px 8px
  group-label:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.mute}"
    typography: "{typography.label}"
    padding: 6px 0px 4px
  kbd:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.mute}"
    typography: "{typography.code}"
    rounded: "{rounded.sm}"
    padding: 0px 5px
  code-inline:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.ink}"
    typography: "{typography.code}"
    rounded: "{rounded.sm}"
    padding: 1px 6px
  code-block:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.ink}"
    typography: "{typography.code}"
    rounded: "{rounded.lg}"
    padding: 14px 16px
  status-bar:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.mute}"
    typography: "{typography.caption}"
    padding: 6px 16px
  tooltip:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.light-ink}"
    typography: "{typography.caption}"
    rounded: "{rounded.md}"
    padding: 8px 11px
  card-hover:
    backgroundColor: "{colors.surface-3}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.lg}"
    padding: 16px
  divider:
    backgroundColor: "{colors.hairline}"
    height: 1px
  divider-strong:
    backgroundColor: "{colors.hairline-strong}"
    height: 1px
  page-glow:
    backgroundColor: "{colors.glow}"
    textColor: "{colors.ink}"
  badge-number:
    backgroundColor: "{colors.primary-deep}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    size: 26px
  badge-ok:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.ok}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: 0px 8px
  badge-warn:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.warn}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: 0px 8px
  badge-info:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.info}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: 0px 8px
  page-light:
    backgroundColor: "{colors.light-canvas}"
    textColor: "{colors.light-ink}"
    typography: "{typography.body-sm}"
  card-light:
    backgroundColor: "{colors.light-surface}"
    textColor: "{colors.light-ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.lg}"
    padding: 16px
  nav-item-light:
    backgroundColor: "{colors.light-surface-2}"
    textColor: "{colors.light-mute}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 8px 10px
  divider-light:
    backgroundColor: "{colors.light-hairline}"
    height: 1px
  button-primary-light:
    backgroundColor: "{colors.light-primary}"
    textColor: "{colors.light-on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 0px 16px
    height: 36px
---

## Overview

Our sites look like the owner's desktop: a black room lit by one green light, and a character standing in it. The page ground is `{colors.canvas}` (`#09090b`, Tailwind zinc-950). A faint green glow (`{colors.glow}`, `#0b2a20`) comes from the top right: `radial-gradient(1200px 700px at 85% -10%, #0b2a20 0%, transparent 60%)`. Behind the content sits one picture from our character library (Itachi, Akaza, Meruem, Vegeta and about 40 more). The pictures are black with teal-emerald brush light and one hot second colour per character.

The UI stays almost colourless so that the picture is the colour. This is the Spotify rule: album art carries the colour, the chrome stays achromatic. One emerald (`{colors.primary}`, `#34d399`) marks what you can act on: the main button, the active place, the focus ring, links, the status dot. Depth comes from a surface ladder and 1px hairlines, not from shadows (the Raycast rule). Text is Inter. Apps (the Studio, the Homepage) are dense at 14px; reading pages (the docs, the blog) are calm at 16-18px.

**Key characteristics**
- Near-black zinc canvas with a green glow at the top right; dark is the brand.
- One character picture per page, behind a scrim that darkens the text side.
- One accent: emerald `#34d399`; dark ink `#022c22` on a filled green button, never white.
- A surface ladder `#09090b` → `#111113` → `#18181b` → `#1f1f23` with hairlines `#27272a` / `#3f3f46`.
- Inter, self-hosted. Headings 600, body 400, labels 12px uppercase 700.
- Radii 6 / 10 / 14 / 16 px and pills; no square cards, no giant pills on buttons.
- Motion 150-300 ms, ease-out, off when the visitor asks for reduced motion.
- Every tap target at least 44 x 44 px on a phone or touch screen.

## Colors

> **Source:** the stylesheets of the homepage, the audio studio and the personal site with its docs. The four files already share the same zinc and emerald values; this file names them once.

### Surface
- **Canvas** (`{colors.canvas}`, `#09090b`): the page ground on every site.
- **Glow** (`{colors.glow}`, `#0b2a20`): the radial light at the top right. It sits on the canvas, under the art.
- **Surface** (`{colors.surface}`, `#111113`): cards, tiles, rail, status bar, callouts.
- **Surface 2** (`{colors.surface-2}`, `#18181b`): inputs, icon buttons, code, hover and active rows, dialogs.
- **Surface 3** (`{colors.surface-3}`, `#1f1f23`): hover on a glass panel; the top step of the ladder.
- **Hairline** (`{colors.hairline}`, `#27272a`): every card edge and divider on a solid surface.
- **Hairline strong** (`{colors.hairline-strong}`, `#3f3f46`): control borders, kbd, figure frames.

### Glass (only over a picture)
When a picture is behind a panel, the panel turns to glass: `color-mix(in oklab, #111113 72-84%, transparent)`, the hairline becomes `color-mix(in oklab, #3f3f46 70%, transparent)`, and `backdrop-filter: blur(14px) saturate(1.2)` is on. Without a picture, panels are solid.

### Text
- **Ink** (`{colors.ink}`, `#f4f4f5`): headings, labels of controls, app body text.
- **Body** (`{colors.body}`, `#d4d4d8`): long reading text (docs, blog). It is softer than ink for long sessions.
- **Mute** (`{colors.mute}`, `#a1a1aa`): metadata, inactive nav, captions. This is the darkest text we allow (WCAG AA on the canvas).

### Accent
- **Primary** (`{colors.primary}`, `#34d399`, emerald-400): the one accent. Main button, active icon, link, focus ring, status dot, selection tint (35 % mix).
- **Primary hover** (`{colors.primary-hover}`, `#6ee7b7`): hover of the main button and of links; code paths and commands in docs.
- **Primary deep** (`{colors.primary-deep}`, `#10b981`): only the end of the badge gradient `linear-gradient(135deg, #6ee7b7, #10b981)` (docs number badges, brand dot).
- **On primary** (`{colors.on-primary}`, `#022c22`): text and icons on a green fill.
- **Soft forms:** fill `rgba(52, 211, 153, 0.10)`, border `rgba(52, 211, 153, 0.35)` for the active TOC row, the selected search result and context callouts.

### Character accent
Each picture in the library has its own `accent` in `index.json` (for example Itachi `#ff4d63`, Vegeta `#ffe94d`, Meruem `#8f4dff`). It may tint decoration tied to that picture only: the 2px dash before a group label, a glow, the picker card. It never colours a button, a link or a state.

### Semantic (state only, never decoration)
- **OK** (`{colors.ok}`, `#6ee7b7`), **Warn** (`{colors.warn}`, `#fbbf24`), **Error** (`{colors.err}`, `#f87171`), **Info** (`{colors.info}`, `#7dd3fc`).
- Each has a soft fill at 10 % and a line at 35-40 % for callouts and chips. Docs meaning: warn = careful or a gate, info = a tip or a prompt to paste.

### Light theme (optional)
Dark is the brand. A site may offer light (the Studio does, through Settings or the system). Then use the `light-*` tokens, and hide the art and the glow. The green fill in light is `#047857` with `#ecfdf5` text (5.5:1); the Studio's `#059669` with white text is only 3.6:1.

## Typography

### Font family
**Inter**, self-hosted as one variable file (weights 400-700), `font-display: swap`. Fallback: `ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif`. Turn on `-webkit-font-smoothing: antialiased`. Use `font-variant-numeric: tabular-nums` on numbers that change (memory, timers, counts). Code uses the system mono stack in `{typography.code}`.

### Hierarchy

| Token | Size | Weight | Line height | Tracking | Use |
|---|---|---|---|---|---|
| `{typography.display}` | 48px (`clamp(2rem, 6vw, 3rem)`) | 600 | 1.08 | -0.025em | One page title per page (docs hero, site home) |
| `{typography.heading-xl}` | 28px (`clamp(1.4rem, 4vw, 1.75rem)`) | 600 | 1.25 | -0.015em | Section heading (docs part, page title in an app) |
| `{typography.heading-lg}` | 22px | 600 | 1.2 | -0.01em | Card title, channel name |
| `{typography.heading-md}` | 18px | 600 | 1.4 | 0 | Sub-heading inside a section |
| `{typography.body-lg}` | 18px | 400 | 1.65 | 0.01em | Long reading (blog post, reader) |
| `{typography.body-md}` | 16px | 400 | 1.7 | 0 | Docs body |
| `{typography.body-sm}` | 14px | 400 | 1.5 | 0 | App body, nav, inputs, card text |
| `{typography.button}` | 14px | 500 | 1.0 | 0 | Every button label |
| `{typography.caption}` | 13px | 400 | 1.4 | 0 | Tile description, metadata, status bar |
| `{typography.label}` | 12px | 700 | 1.4 | 0.08em, uppercase | Group label, table header, kicker, TOC title |
| `{typography.micro}` | 10px | 500 | 1.0 | 0 | Rail key hints, phone tab labels |
| `{typography.code}` | 13.5px | 400 | 1.55 | 0 | Inline code, code blocks, kbd, paths |

### Principles
- **Mid weight headings.** Headings are 600 with slight negative tracking. 700 is for labels, numbers and the wordmark only.
- **One label voice.** Every small uppercase label uses `{typography.label}`. This replaces four slightly different label styles in use today.
- **App dense, docs calm.** Apps default to 14px; docs to 16px / 1.7; long reads to 18px / 1.65 at 65ch.
- **Line length.** Reading text stays under 65ch; the docs column is at most 780px. Tables, code and callouts may use the full column.
- **Display text** may use the docs gradient `linear-gradient(180deg, #fafafa 30%, #a1a1aa)` clipped to text, once per page.

## Layout

### Spacing system
- **Base unit:** 4px (the Tailwind scale). Common steps: 8px (gap between controls), 12px (gap in a card), 16px (card padding, page gutter on a phone), 24px (page gutter on a desktop), 32px (page padding in an app view).
- **Section rhythm:** `{spacing.section}` (64px) between major blocks on reading pages; 48px on a phone. `{spacing.huge}` (96px) only before the footer or under a hero.

### Grid and container
- **App shell (Studio):** a left rail 192px wide (icons + labels + key hints 1-8), main area fills the rest, a player bar and a status bar at the bottom. On a phone the rail becomes a bottom bar with an icon over a short label.
- **Dashboard (Homepage):** one row per group in the owner's order, 1-5 tiles per row; every row is one column on a phone. Channel cards are a 5:7 grid of banner and body.
- **Docs:** three columns at 1280px and up (contents 250px | article max 780px | on this page 220px), two columns at 1024px, one column with a drawer below. A 52px sticky top bar holds the brand, the search trigger and the menu.
- **Personal site:** one column, `max-w-2xl` (672px), sticky top nav 56px tall with blur.

### Whitespace philosophy
Apps pack content densely, like Spotify: the dark ground gives rest without big gaps. Reading pages breathe: 1.7 line height, 62-65ch lines, 64px between sections. The art side of the page stays empty on a wide screen; content lives on the darkened side.

## Elevation & Depth

| Level | Treatment | Use |
|---|---|---|
| 0, ground | `{colors.canvas}` + glow + art layer | Page |
| 1, surface | `{colors.surface}` + 1px `{colors.hairline}` | Cards, tiles, rail, bars, callouts, tables |
| 2, raised | `{colors.surface-2}` + 1px `{colors.hairline-strong}` | Inputs, icon buttons, code, hover rows |
| 3, float | `{colors.surface-2}` + 1px `{colors.hairline-strong}` + `0 30px 80px rgba(0,0,0,0.6)` | Command palette, dialogs, menus, image zoom |
| Figure | `0 1px 0 rgba(255,255,255,0.04) inset, 0 18px 50px rgba(0,0,0,0.45)` | Screenshots in docs |

**Shadow rule.** Cards and tiles have no shadow: the ladder and the hairline make the depth (Raycast). Floating layers get one heavy shadow, because a light shadow is invisible on black (Spotify). A green glow shadow (`0 0 0 4px rgba(52,211,153,0.12), 0 6px 18px rgba(52,211,153,0.18)`) is for the numbered docs badges only.

### The art layer
- One `position: fixed; inset: 0; z-index: -1; pointer-events: none` layer with the picture (`object-fit: cover`) and a scrim above it.
- **Scrim:** a horizontal gradient from the canvas colour at the text side to clear at the character side, plus a bottom fade `linear-gradient(0deg, canvas 60-70%, transparent 22-25%)`. The `side` field of the picture (`left`, `right`, `center`) flips or evens the gradient.
- **Strengths:** `subtle` (art 0.55, veil 94 %), `normal` (art 0.9, veil 88 %), `strong` (art 1.0, veil 70 %). Dashboards and app home pages use `normal`; reading pages use `subtle`.
- **Phone (below 768px):** one even veil over the whole picture (veil minus 12 %), and the 900px-wide picture file instead of the full one.
- The picture fades in over 700ms after load. Print and the light theme hide it.

## Shapes

### Border radius scale

| Token | Value | Use |
|---|---|---|
| `{rounded.xs}` | 4px | Focus ring corner, tiny tags |
| `{rounded.sm}` | 6px | Inline code, kbd, small controls inside a row |
| `{rounded.md}` | 10px | Buttons, inputs, icon buttons, nav rows, tooltips, link chips |
| `{rounded.lg}` | 14px | Cards, tiles, panels, callouts, code blocks, tables, figures |
| `{rounded.xl}` | 16px | Command palette, dialogs, large picture panels |
| `{rounded.full}` | 9999px | Filter chips, badges, avatars, the play button |

A callout with a 3px coloured left edge keeps that edge square: `border-radius: 0 14px 14px 0`.

### Picture geometry
- Backdrops are 16:9 masters, cut to cover; thumbs for pickers are 4:5 at `{rounded.md}`.
- Channel avatars are 64px circles with a 2px gradient ring in the channel's two colours.
- Banners are 960x540, avatars 240px square, both WebP.

## Components

### Buttons
- **`button-primary`:** emerald fill, `{colors.on-primary}` text, 36px tall (44px on a phone), `{rounded.md}`. Hover goes to `{colors.primary-hover}`. **One filled green button per view** (Supabase): the action the page exists for.
- **`button-outline`:** surface fill, 1px hairline, ink text; hover to surface-2. The default button.
- **`button-ghost`:** no fill, mute text; hover fills surface-2 and turns the text ink. For toolbars.
- **`button-danger`:** like outline with `{colors.err}` text. Never a red fill.
- **`button-icon`:** 44px square, surface-2, `{rounded.md}`; hover border `primary` at 35 %, icon turns emerald.
- **`button-play`:** a green circle with a dark icon (Spotify's round play control).
- A busy button shows a spinner before its label and is disabled. Disabled is 50 % opacity.

### Inputs and search
- **`text-input`:** surface-2, 1px hairline-strong, 40px tall (44px on touch), `{rounded.md}`. Focus: the border turns emerald, no glow.
- **`search-trigger`:** looks like an input with a magnifier, the hint text and a kbd (`Ctrl K`). It opens the command palette.
- **`command-palette`:** one shared pattern for the Studio (Ctrl+K), the docs search and the Homepage quick search (Raycast). Float level, 680px wide at most, chips for scopes, results 9x12px rows, the selected row in the soft emerald fill with an inset emerald line.

### Cards and tiles
- **`card`:** surface, 1px hairline, `{rounded.lg}`, 16px padding, no shadow. Hover (if it is a link): border to emerald at 60 % mix, surface to surface-2, 200ms.
- **`tile`** (Homepage): a card at least 56px tall with icon, name (600) and a 13px mute description; the whole tile is the link.
- **Channel card:** banner left, avatar and name right, one 44px link chip per platform; a 2px top bar in the channel's two colours.

### Navigation
- **Rail / sidebar row (`nav-item`):** 14px, mute; active row surface-2, ink text, emerald icon; key hint in micro mono at the right.
- **Docs contents:** a 2px left line per row; the active row turns emerald with the soft fill and a `0 8px 8px 0` radius.
- **Top bar:** canvas at 90 % with `backdrop-blur-md`, 1px hairline below, sticky. One sticky bar per page, never two.
- **Group label:** `{typography.label}` in mute, after a 0.6rem x 2px dash in the character accent.

### Callouts (docs)
- **Context** (why): emerald left edge, soft emerald fill. **Tip / prompt** (shortcut, paste into Claude Code): info blue. **Warn / gate** (careful, the owner's yes): amber. **Quick** (the short answer): surface with a faint emerald glow.

### Chips, badges, kbd, code
- **`chip`:** pill, surface-2, 1px hairline-strong, 13px; active chip goes one surface step up and turns ink.
- **`badge`:** pill, 12px label type, coloured text on its soft fill.
- **`kbd`:** 11px mono, surface-2, 1px hairline-strong with a 2px bottom border (a key cap, as Raycast does), `{rounded.sm}`.
- **`code-inline`:** mono at 0.86em (12px at least), surface-2 fill with a hairline-strong border, `{rounded.sm}`. **`code-block`:** surface-2, hairline, `{rounded.lg}`, a Copy button at the top right.

### Status and feedback
- **Status bar:** 12-13px mute text on surface, links turn ink on hover; warnings in amber with an icon.
- **Toast:** slides in from the right in 300ms, slides out in 300ms.
- **Skeleton:** surface-2 block with `animate-pulse`, same radius as the thing it stands for.
- **Tooltip:** light pill on dark (`#f4f4f5` on the page, `#18181b` text), float shadow.

## Do's and Don'ts

### Do
- Start every page on `#09090b` with the green glow, then the art layer, then the content.
- Let the picture bring the colour; keep the chrome zinc and emerald.
- Keep emerald for things you can act on, and keep it scarce: one filled green button per view.
- Put dark ink `#022c22` on green fills.
- Build depth with the surface ladder and hairlines; give a shadow only to floating layers.
- Self-host Inter; use 600 for headings and the one label style for small caps.
- Give every tap target 44 x 44 px on touch (an invisible `::after` hit area is fine).
- Show a 2px emerald focus ring with a 2px offset on every focusable element.
- Turn all motion off under `prefers-reduced-motion: reduce`.

### Don't
- Don't put the emerald on large backgrounds or use it as decoration.
- Don't add a second UI accent; amber, red and blue are states, not brand colours.
- Don't use a character accent on a button, a link or a state.
- Don't put white text on a green fill.
- Don't put text over the bright side of a picture without the scrim.
- Don't give cards a drop shadow, and don't use pill-shaped primary buttons.
- Don't use text darker than `#a1a1aa` on the canvas.
- Don't stack two sticky bars.

## Where our sites disagree today, and the rule

| What | The homepage | The audio studio | The personal site + docs | The rule |
|---|---|---|---|---|
| Inter font | Named, not loaded (system font shows) | Named, not loaded | Self-hosted variable file | Self-host the one Inter variable WOFF2 on every site |
| Card radius | Tiles 14px, chips 10px | Buttons 6px, cards 8px, panels 12px | Callouts 14px, tables and code 12px, inputs 8-10px, search 16px | `md` 10px for controls, `lg` 14px for cards, `xl` 16px for floats |
| Panels | Glass at 84 % with blur | Solid; glass only with a backdrop | Solid | Solid by default; glass only when a picture is behind |
| Art strength | Opacity 0.9, own scrim | subtle / normal / strong setting | Docs 0.42 (home 0.7), phone 0.22; site home has no art | One art layer with three strengths; dashboards `normal`, reading pages `subtle`, the personal home gets one too |
| Which picture | New one each day, `?bg=` override | The visitor picks | Fixed per page (hash of the slug) | One manifest, one picker: `?bg=` → the visitor's pick → per page (docs) or per day (dashboards) |
| Picture set | 44 (Studio list) | 44 | 28 | Every site reads the same library manifest |
| Glow | None (art only) | Yes | Yes | The glow is under every page, art above it |
| Small labels | 12.5px / 600 / 0.14em | 10-12px mixed | 12px / 700 / 0.06-0.1em; blog tables 12px / 600 / 0.05em | One `label`: 12px / 700 / uppercase / 0.08em |
| Headings | Tile names 600, channel names 700 | 600 | Personal home 700 bold; docs 600 | Headings 600; 700 only for labels, numbers, wordmark |
| Motion | 200ms | 150-200ms, art 700ms | 150ms, toasts 300ms | 150ms colour, 200ms move, 300ms enter or leave, 700ms art fade, ease-out |
| Mono stack | none | `ui-monospace, Cascadia Code, SF Mono, Consolas` | `ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono` | The `{typography.code}` stack everywhere |
| Phone breakpoint | 767px | 560px and 768px | 640px, 767px and 1023px | Tailwind steps only: 640, 768, 1024, 1280 |
| Light theme | none | Full light set | none | Dark is the brand; light is optional and uses the `light-*` tokens |
| Character accent | Tints the group-label dash | Tints the picker | Not used | Decoration tied to the picture only, never a control |

What all four already do the same, and keep: the zinc canvas `#09090b`, emerald `#34d399`, hairline `#27272a`, mute `#a1a1aa`, the 2px emerald focus ring, the 44px touch rule, reduced motion, the green selection tint, and the scrim that darkens the text side of the picture.

## Responsive Behavior

### Breakpoints

| Name | Width | Changes |
|---|---|---|
| Phone | < 640px | One column; 16px gutters; Copy buttons get their own row; display 32px |
| Large phone | 640-767px | Still one column; art gets one even veil |
| Tablet | 768-1023px | App rail on the left; Homepage rows get columns; docs contents in a drawer |
| Desktop | 1024-1279px | Docs two columns; channel cards 5:7 |
| Wide | ≥ 1280px | Docs three columns; the art's character fully visible on the right |

### Touch targets
On `(pointer: coarse)` or below 640px, every button, link, tab, summary and checkbox label reaches 44 x 44 px. Small inline items keep their look and get an invisible `::after` hit area. Inputs and selects are at least 44px tall.

### Collapsing strategy
- App rail → bottom bar (icon over a short label).
- Homepage rows → one column; channel card banner on top at 16:7.
- Docs: three columns → two → one with a contents drawer under the top bar.
- Display type steps 48 → 40 → 32px through `clamp()`.

### Image behavior
Each backdrop has a full file and a 900px-wide file (about 65 KB); phones load the small one. Pictures are WebP. A missing picture leaves the plain black-green page; nothing breaks.

## Iteration Guide

1. Copy the tokens into the site's CSS as custom properties (`--bg`, `--surface`, `--line`, `--ink`, `--mute`, `--acc`), the way the Studio's `index.css` does. Tailwind 4 sites map them with `@theme inline`.
2. Build one component at a time and name its token (`{rounded.lg}`, `{colors.surface-2}`); do not paraphrase values.
3. Add the art layer last; check the text side against the scrim at 375px, 768px and 1440px.
4. Before you add a token, try the ladder, the hairline, 10/14px radius and the emerald first.
5. Run `npx @google/design.md lint DESIGN.md` after an edit to this file.
6. When two of our sites disagree, the table above names the rule; fix the site, not the rule.

## Known Gaps

- The art library manifest and the shared loader do not exist yet; today each site keeps its own list (Studio `public/backdrops/index.json`, docs `docs-art.ts`, Homepage reads the Studio copy).
- Only the green-black theme pack exists. Other packs (yellow-white, red-white, blue-black and black-and-white pairs) will add a token set and a picture set each.
- Homepage HTML comes from the Homepage app; only `custom.css` and `custom.js` are ours, so its markup follows these rules only as far as CSS reaches.
- The light theme is complete in the Studio only.
