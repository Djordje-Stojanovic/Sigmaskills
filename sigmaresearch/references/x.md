# X in Chrome

Adapted from the owner's `research-access.md` recipe, tested 2026-10-04. Availability depends on the current tools and owner's session. Follow [access boundaries](../SKILL.md#access-boundaries).

1. Discover **Claude in Chrome** tools. If they are absent, report that X reading is unavailable here. Do not substitute an empty fetch result for evidence or assume another browser has the owner's session.
2. Use the owner's existing signed-in session only. If it is gone or a login wall appears, report that the owner must restore the session themselves for a future run. The agent never signs in or handles credentials.
3. Create a research tab. Combine the topic with `min_faves:200 since:YYYY-MM-DD`, then URL-encode the **whole query**. Navigate to `https://x.com/search?q=ENCODED_QUERY&f=top`. Adjust the threshold/date to the user's scope; these are selection filters, not quality guarantees. Use `f=live` for newest posts.
4. Allow the page about five seconds to render, then use the available browser JavaScript-reading tool. Read each visible `article`: `[data-testid="tweetText"]` text, `time[datetime]` date and its `a[href*="/status/"]` permalink. Generic page text missed posts in the tested recipe. Selectors may change; inspect the rendered page if they return nothing. Do not call an empty result a successful read.
5. Open relevant status permalinks for threads and visible replies. Scroll and read more within the requested depth. Label omitted, unavailable or collapsed material as partial; the browser view does not prove all replies were read.
6. Close the tab you created. Leave the owner's other tabs intact.

Stop on a bot check, access denial, 403 or 429. Do not replay requests, extract session tokens, invoke private endpoints or try mirrors after a block. If no permitted route succeeds, finish with an explicit X access gap and sources from other platforms.
