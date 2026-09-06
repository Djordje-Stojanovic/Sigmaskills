# Use the Emberforge visual language

The Sigma Installer will use the Emberforge prototype as its visual foundation: an intense molten Sigma reveal followed by a disciplined terminal interface using the exact warm LAPI WezTerm palette. The production UI will harden Emberforge for accessibility, resizing, terminal compatibility, copy accuracy, and error states rather than blend it with Prismgrid or Monolith.

## Current interactive layout

The installer keeps the warm LAPI palette and uses a compact Sigma reveal with a stage label. Skill selection uses short rows plus a bounded focused description. Destination selection windows rows to the terminal height, including wrapped text and footer space. Static and plain output writes a page only when its content changes. This keeps the Emberforge identity while making redirected and short-terminal sessions readable and finite.

## Primary source

The throwaway prototype is at `C:\AI\TEMP\sigmaskills-installer-prototype` and runs with `npm start`.
