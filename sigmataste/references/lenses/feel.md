# Feel

## What it sees

The unseen details that, together, make software feel cared for. Each one alone goes unnoticed; their sum is what people call polish. Look at every state, not just the happy screenshot: rest, hover, press, focus, loading, empty, error, long content, success.

## Tells

- Buttons with no press state; links and buttons with no hover state on desktop.
- Focus rings removed, or the browser default on a styled page; sticky headers that cover the focused field.
- Empty states that show a broken layout or nothing; errors that only say "Something went wrong".
- Loading with a layout jump when content arrives; images without width and height.
- Long names that break the card; flex children that do not truncate.
- Tooltips that each wait again after the first one is open.
- Filters, tabs and open panels lost on reload because the URL does not hold them.
- Destructive actions with no confirm and no undo.
- Native controls (select, scrollbar) unthemed in dark mode.

## Fix moves

- Design every state of the main component once, then reuse it.
- `:focus-visible` rings in the brand's style; keep the focused element visible under sticky bars.
- Empty state as an invitation to act; error that says what happened and how to fix it.
- Skeletons sized like the content; explicit media dimensions.
- Truncate or wrap long content on purpose; test short, average and very long input.
- Put view state in the URL; undo window for destructive actions.
- `color-scheme` set for the theme so native controls follow.

## Verify

- Tab through the main flow with the keyboard only.
- Load with slow network and with empty data; paste a very long name.
- Screenshot each state of the main component side by side.

## Source and what changed

From emilkowalski `emil-design-eng` (unseen details compound, press scale, tooltip timing; MIT) and Vercel `web-design-guidelines` (focus, content handling, navigation and state, dark mode rules; MIT). Improved: the rules are grouped by the state a person meets, with one walkthrough to check them all.
