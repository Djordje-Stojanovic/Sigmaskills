# Colour

## What it sees

Whether each colour has a job. Which colour holds the surface, which supports, where is the accent? An accent in ten places means nothing; on the one action and one detail it means "here". Mood comes more from lightness and chroma than from hue: a muted palette reads calm in any hue. In a story (film, deck, brand), a colour gains meaning by being tied to one subject and repeated.

## Tells

- The accent on links, borders, badges, icons, focus rings and headings all at once.
- Three or more saturated colours of equal weight ("three gorillas fighting").
- Grey text on a coloured ground; text that passes only on one theme.
- Hand-picked hex values for hover and dark mode that drift from the base colour.
- Gradients through RGB or HSL that go muddy grey in the middle.
- A palette that fights the subject's own material (neon on a craft product, pastel on a war documentary).
- Light or dark chosen from habit, not from where it is seen (dark room, bright office, phone in sunlight).

## Fix moves

- Assign proportions: about 60 % surface, 30 % support, 10 % accent, and write the accent's one meaning.
- Build ramps in OKLCH so steps are even across hues; derive hover and dark variants from the base (`oklch(from var(--brand) ...)`, `color-mix(in oklab, ...)`).
- Tokens in layers: raw palette, then roles (surface, text, accent, success, warning, danger), then components use roles only.
- Pull the palette from the subject's world (its materials, its place, its light).
- For a story, tie one colour to one subject and let it change when the subject changes.

## Verify

- A greyscale screenshot: hierarchy should survive on lightness alone.
- Count where the accent appears; each place should be "the action" or "the one detail".
- Measure text contrast in both themes with a WCAG or APCA tool.

## Source and what changed

From meodai `skill.color-expert` (OKLCH, token graph, character-first harmony, 60-30-10, colour association in stories after Lewis Bond; CC-BY-4.0) and Anthropic `frontend-design` (dominant colour with a sharp accent; Apache-2.0). Improved: the encyclopedia is cut to the decisions that change how a target looks, with a greyscale and accent-count check.
