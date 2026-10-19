# Charts

## What it sees

Whether each chart, metric tile and table answers one question at a glance. Start from the question (a trend, a comparison, a share, an outlier), then check the form fits it and the answer is visible without reading the axis. Layers: a title that states the point, context (dates, units, scope), the visual, exact values for those who need them, the source.

## Tells

- A chart titled with a topic ("Revenue") instead of the finding ("Revenue doubled since March").
- The default library palette, rainbow or jet colour ramps; categories that differ only by hue.
- Pie charts with many slices; 3D; dual axes that invent a correlation.
- Every metric tile identical, each with its own sparkline, nothing standing out.
- Gridlines, borders and legends louder than the data.
- A chart where a sentence or a small table would answer faster.
- Numbers without units or dates; no source.

## Fix moves

- Write the question first; choose the form from it (line for trend, bar for comparison, table for exact values, a sentence for one number).
- Title states the point; label lines directly instead of a legend.
- Mute the frame (gridlines, axes) and let the data carry the colour; highlight the one series that matters, grey the rest.
- Sequential data on an even-lightness ramp (OKLCH); categorical colours with a second cue (labels, borders, patterns) since only about three colours can hold contrast with each other.
- Give the most important metric more size than the rest.
- Add the exact values in a table or on hover, and the source.

## Verify

- Ask "what is the answer?" of the chart alone; it should be the title.
- Greyscale and colour-blind simulation screenshots: series still tell apart.

## Source and what changed

From meodai `skill.color-expert` (flat-derivative ramps, the border trick for chart colours; CC-BY-4.0), mgifford `accessibility-skills` charts guide (start from the user's question, layered information; AGPL-3.0, ideas only), and chrisvoncsefalvay `claude-d3js-skill` (when a custom chart earns its cost). Improved: one question-first test for dashboards, decks and reports.
