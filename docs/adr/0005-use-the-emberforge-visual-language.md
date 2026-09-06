# Use the Emberforge visual language

The Sigma Installer uses Emberforge's warm LAPI WezTerm palette. The original prototype included a molten Sigma reveal. The decision below supersedes that animation after installer repetition and terminal overflow were reported.

## Current interactive layout

Open directly to a small Sigma heading and stage progress. Use short skill rows with bounded focused details. Show at most eight destination rows and keep focus and controls within the terminal height. Long confirmation paths wrap onto navigable pages. Static and plain terminals accept one command per line and print a page only after meaningful changes. Reduced motion keeps the same interactive picker because there is no animation. This follows the compact interaction of [Vercel's searchable picker](https://github.com/vercel-labs/skills/blob/main/src/prompts/search-multiselect.ts), while retaining Sigma's installation and preservation engine.

## Primary source

The throwaway prototype is at `C:\AI\TEMP\sigmaskills-installer-prototype` and runs with `npm start`.
