# Motion

## What it sees

Whether each movement has a reason, and whether it should move at all. Valid reasons: show what changed, keep space consistent (it leaves the way it came), confirm an action, explain how something works, avoid a jarring jump. How often people see it decides how much it moves: a thing seen a hundred times a day should not animate; a first-run moment may delight. One orchestrated moment beats scattered effects.

## Tells

- The same fade-and-rise entrance on every section or card.
- Hover lift on every card; hover effects on touch screens.
- Animation on keyboard actions and command palettes (feels slow).
- Things that grow from nothing (`scale(0)`), or popovers that grow from their centre instead of their trigger.
- `transition: all`; animating width, height, margin or padding.
- Slow UI motion (well over a third of a second for menus and toggles); enter and exit at the same speed.
- In video: a slow push on every still whether or not it shows something new; nothing new on screen for a long stretch.
- No reduced-motion version.

## Fix moves

- Write the reason for each animation in one line; cut the ones without a reason or seen many times a day.
- Keep one signature moment (the page load, one reveal, the hook) and make the rest quiet.
- Defaults for UI where the brand has none: ease-out for enter, exit faster than enter, small scale (0.95 and up) with opacity, origin at the trigger, transform and opacity only, a press state that scales slightly.
- Gate hover effects behind `(hover: hover) and (pointer: fine)`; give a reduced-motion variant that keeps fades and drops movement.
- In video, move the camera only when the move shows something new.

## Verify

- Watch at quarter speed (DevTools animation panel, or a frame-by-frame scrub for video).
- Turn on reduced motion and use the page.
- Count animations per screen before and after.

## Source and what changed

From emilkowalski `emil-design-eng` (should it animate at all, purpose, easing, origin, speed; MIT), Anthropic `frontend-design` (one orchestrated moment; Apache-2.0) and Vercel `web-design-guidelines` (animation rules; MIT). Improved: the numbers are defaults the brand overrides, the lens covers video camera moves, and each animation needs a one-line reason.
