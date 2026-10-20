---
version: alpha
name: Maze Runner
description: "A cool near-black ground with one amber accent, Inter, soft corners; the amber carries the game."

colors:
  canvas: "#090a0c"
  glow: "#2b1d08"
  surface: "#0f1114"
  surface-2: "#16191d"
  surface-3: "#1d2026"
  hairline: "#23282f"
  hairline-strong: "#39414c"
  ink: "#f3f5f6"
  body: "#d2d5db"
  mute: "#939ca9"
  primary: "#e8a33d"
  primary-hover: "#edb96b"
  primary-deep: "#e1911b"
  on-primary: "#241804"
  ok: "#64f7ad"
  warn: "#f7cd64"
  err: "#f77064"
  info: "#64c8f7"
  light-canvas: "#f9fafb"
  light-glow: "#f9fafb"
  light-surface: "#ffffff"
  light-surface-2: "#f3f5f6"
  light-surface-3: "#ebedf0"
  light-hairline: "#e2e5e9"
  light-hairline-strong: "#c5cbd3"
  light-ink: "#16191d"
  light-body: "#353c46"
  light-mute: "#586474"
  light-primary: "#a26813"
  light-primary-hover: "#875610"
  light-primary-deep: "#6b450d"
  light-on-primary: "#ffffff"
  light-ok: "#0a8447"
  light-warn: "#a16a0d"
  light-err: "#bd1e0f"
  light-info: "#0f74bd"

typography:
  display:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: 48px
    fontWeight: 600
    lineHeight: 1.08
    letterSpacing: -0.025em
  heading-xl:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: 28px
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: -0.015em
  heading-lg:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: 22px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: -0.01em
  heading-md:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0
  body-lg:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: 18px
    fontWeight: 400
    lineHeight: 1.65
    letterSpacing: 0.01em
  body-md:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.7
    letterSpacing: 0
  body-sm:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0
  button:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.0
    letterSpacing: 0
  caption:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0
  label:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: 12px
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: 0.08em
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
  page:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.body}"
    typography: "{typography.body-md}"
  page-glow:
    backgroundColor: "{colors.glow}"
    textColor: "{colors.body}"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 0px 16px
    height: 40px
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 0px 16px
    height: 40px
  button-primary-pressed:
    backgroundColor: "{colors.primary-deep}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 0px 16px
    height: 40px
  button-outline:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 0px 16px
    height: 40px
  button-ghost:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.mute}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 0px 12px
    height: 40px
  text-input:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 0px 12px
    height: 40px
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.lg}"
    padding: 16px
  card-raised:
    backgroundColor: "{colors.surface-3}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.lg}"
    padding: 16px
  chip:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.body}"
    typography: "{typography.caption}"
    rounded: "{rounded.full}"
    padding: 0px 12px
    height: 28px
  divider:
    backgroundColor: "{colors.hairline}"
    textColor: "{colors.ink}"
    height: 1px
  divider-strong:
    backgroundColor: "{colors.hairline-strong}"
    textColor: "{colors.ink}"
    height: 1px
  status-ok:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ok}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: 0px 12px
    height: 24px
  status-warn:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.warn}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: 0px 12px
    height: 24px
  status-err:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.err}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: 0px 12px
    height: 24px
  status-info:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.info}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: 0px 12px
    height: 24px
  light-page:
    backgroundColor: "{colors.light-canvas}"
    textColor: "{colors.light-body}"
    typography: "{typography.body-md}"
  light-page-glow:
    backgroundColor: "{colors.light-glow}"
    textColor: "{colors.light-body}"
  light-button-primary:
    backgroundColor: "{colors.light-primary}"
    textColor: "{colors.light-on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 0px 16px
    height: 40px
  light-button-primary-hover:
    backgroundColor: "{colors.light-primary-hover}"
    textColor: "{colors.light-on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 0px 16px
    height: 40px
  light-button-primary-pressed:
    backgroundColor: "{colors.light-primary-deep}"
    textColor: "{colors.light-on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 0px 16px
    height: 40px
  light-button-outline:
    backgroundColor: "{colors.light-surface}"
    textColor: "{colors.light-ink}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 0px 16px
    height: 40px
  light-button-ghost:
    backgroundColor: "{colors.light-canvas}"
    textColor: "{colors.light-mute}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 0px 12px
    height: 40px
  light-text-input:
    backgroundColor: "{colors.light-surface-2}"
    textColor: "{colors.light-ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 0px 12px
    height: 40px
  light-card:
    backgroundColor: "{colors.light-surface}"
    textColor: "{colors.light-ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.lg}"
    padding: 16px
  light-card-raised:
    backgroundColor: "{colors.light-surface-3}"
    textColor: "{colors.light-ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.lg}"
    padding: 16px
  light-chip:
    backgroundColor: "{colors.light-surface-2}"
    textColor: "{colors.light-body}"
    typography: "{typography.caption}"
    rounded: "{rounded.full}"
    padding: 0px 12px
    height: 28px
  light-divider:
    backgroundColor: "{colors.light-hairline}"
    textColor: "{colors.light-ink}"
    height: 1px
  light-divider-strong:
    backgroundColor: "{colors.light-hairline-strong}"
    textColor: "{colors.light-ink}"
    height: 1px
  light-status-ok:
    backgroundColor: "{colors.light-surface}"
    textColor: "{colors.light-ok}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: 0px 12px
    height: 24px
  light-status-warn:
    backgroundColor: "{colors.light-surface}"
    textColor: "{colors.light-warn}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: 0px 12px
    height: 24px
  light-status-err:
    backgroundColor: "{colors.light-surface}"
    textColor: "{colors.light-err}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: 0px 12px
    height: 24px
  light-status-info:
    backgroundColor: "{colors.light-surface}"
    textColor: "{colors.light-info}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: 0px 12px
    height: 24px

---

## Overview

A terminal maze game. Players are quick and impatient; the mood word is focused. The memorable thing is the single amber snake against a calm blue-black board.

## Colors

- **Canvas and surfaces** (`canvas`, `surface`, `surface-2`, `surface-3`): a tinted ladder, each step one notch lighter; borders are `hairline`.
- **Ink, body, mute**: text roles. `mute` is the quietest text that still passes 4.5:1 on a surface.
- **Primary**: the one accent. One filled primary button per view. `on-primary` is the text on it.
- **Status**: `ok`, `warn`, `err`, `info`, only for state.
- **Light tokens** (`light-*`) exist for a light theme; dark is the default.
- **Packs**: other accents live in `design.packs.json` (`sigmadesign.py pack`); each pack is checked for contrast.

## Typography

Inter for everything; the scale is `typography` above; paragraphs stay under 62 characters wide; headings are weight 600 in sentence case.

## Layout

One column under 1080 px, left aligned; the board is centred; spacing steps come from `spacing`; breakpoint at 640 px.

## Components

Button, card, input and chip are defined above. The score card uses `card` with the `label` type.

## Do's and Don'ts

- Do use `var(--token)`; do not write a colour literal in page CSS.
- Do keep one filled primary button per view; do not add a second accent.
- Do keep touch targets at least 44 px; do not remove the focus ring.

## Responsive Behavior

At 375 px the grid is one column and the topbar wraps; the smallest width tested is 375 px.

## Iteration Guide

Change a value here, run `python sigmadesign.py build DESIGN.md --out <dir>`, run `check`, look at `index.html`.
