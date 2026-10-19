# Everyone

## What it sees

Whether the design holds up for people who see, move or read differently, and in the conditions people really use it: low vision, colour blindness, keyboard only, a screen reader, reduced motion, zoom, a phone in sunlight, both themes. Here access is part of taste: a design that breaks for them is unfinished.

## Tells

- Text contrast that passes in one theme only, or not at all; meaning carried by colour alone (red and green status dots).
- Zoom disabled; layout that breaks at 200 % zoom or on a narrow phone.
- Icon-only buttons with no name; images with no text alternative; decorative images that a screen reader announces.
- Click handlers on `div`s; custom widgets that the keyboard cannot reach.
- A theme switch that changes the theme as focus moves over the options.
- Video with no captions; motion that plays forever with no pause.
- Headings that skip levels; no skip link on long pages.

## Fix moves

- Fix contrast through the colour roles (see [colour](colour.md)), in both themes and forced colours.
- Add a second cue to colour: an icon, a label, a pattern.
- Native elements first (`button`, `a`, `label`, `table`), then ARIA only where native cannot.
- Names for icon buttons; `alt` that states the point of an image in context, empty `alt` for decoration.
- Captions for video; a pause for motion longer than a few seconds; a reduced-motion variant.
- A theme picker that changes only on explicit press, with all options visible.

## Verify

- Run an automated scan (axe-core or the host's equivalent) on the main pages; read the serious and critical items.
- Keyboard-only and 200 % zoom walk through the main flow.
- Contrast measured in both themes.

## Source and what changed

From mgifford `accessibility-skills` (light and dark mode, charts, layered alternatives; AGPL-3.0, ideas only, no text copied), airowe `claude-a11y-skill` (axe-core runtime scan), and Vercel `web-design-guidelines` (accessibility and focus rules; MIT). Improved: framed as part of taste, cut to the items that change what people see and can do.
