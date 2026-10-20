# Looking checklist

Do these on the sample page and on one real page, in dark, light and each pack. A screenshot is evidence; an exit code is not.

| Check | How | Done when |
|---|---|---|
| Contrast | `python scripts/sigmadesign.py check DESIGN.md --out <build>` | exit 0 |
| Phone width | 375 px wide; `document.documentElement.scrollWidth` | equals 375, no sideways scroll |
| Desktop | 1440 px | content in a column under 1100 px; lines under 80 characters |
| Touch targets | buttons, links, chips | at least 44 px high on touch screens (the sample uses 44 px buttons; chips 28 px are for dense desktop rows only) |
| Focus | press Tab through the page | every control shows the 2 px accent ring |
| Console | open the page | no errors, no failed font or CSS request |
| Motion | `prefers-reduced-motion` | motion off; the generated CSS already does it, so do not add animation outside `components.css` |
| Fonts | the named family | the file loads from the site itself; the fallback stack looks acceptable |
| One accent | scan the page | one filled primary button per view; state colours only on state |
| Packs | open `?theme=<pack>` | text readable, buttons visible, nothing stuck on a dark value |
| Pictures | when the system has an art layer | text sits on the calm side; a scrim keeps contrast over the brightest part |

When a check fails, fix the token or the component, not the page.

For a screenshot without a browser pane, use Playwright or headless Chrome: `chrome --headless --screenshot=out.png --window-size=1440,1000 file:///.../index.html`. A page that loads ES modules needs a local server (`python -m http.server`); stop it when done.

## Lint

`npx @google/design.md lint DESIGN.md` prints JSON with `errors`, `warnings` and `infos`; the target is 0 errors and 0 warnings (the generated components reference every colour token, so a warning means you added a token no component uses). Some shells print nothing from `npx` here; then run `npm i @google/design.md` in a scratch folder and call its `design.md` binary on the file.
