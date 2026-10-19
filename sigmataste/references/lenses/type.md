# Type

## What it sees

Whether type does the hierarchy before anyone reads. Heading, body, label and data roles should tell apart at a glance. The jump from the largest text to the next is decisive. One family, or two that are clearly different. The same role looks the same everywhere. The type itself can be the design: a headline set with intent is an active element, not a container for words.

## Tells

- Sizes one small step apart (32, 28, 24, 20) doing four jobs badly.
- Three or more families, or two that look almost the same.
- Body lines longer than about 80 characters on a desktop page.
- A headline that leaves one orphan word on its last line.
- All-caps labels with wide tracking everywhere.
- Numbers in a table or metric row that jump as they change (proportional figures).
- Three dots instead of an ellipsis; straight quotes where the brand uses curly ones.
- Slides or thumbnails with text too small to read at the real viewing size.

## Fix moves

- Set a type scale with few, decisive steps (for example 1, 1.25, 2, 3.5 of the body size), and map each role to one step.
- One family with clear weights, or one display face plus one text face that contrast strongly.
- Measure: body 45 to 80 characters per line; a little more line height for serif body.
- `text-wrap: balance` on headings, `text-wrap: pretty` on body, where the stack supports it.
- `font-variant-numeric: tabular-nums` for numbers that compare or change.
- Size slide and thumbnail text for the far seat and the phone feed, then check it there.

## Verify

- A screenshot with all text replaced by grey bars: the roles should still read.
- Measure line length on the widest layout.
- The text at real size on a phone, a projector, or the feed.

## Source and what changed

From Anthropic `frontend-design` (type scale after The Elements of Typographic Style, one or two families, line length; Apache-2.0) and Vercel `web-design-guidelines` (typography rules: ellipsis, tabular numbers, balanced headings; MIT). Improved: one lens for page, slide, thumbnail and terminal, with a grey-bar test for roles.
