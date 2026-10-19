# X in Chrome

X is read only through the owner's already signed-in Chrome. The script never contacts X; it normalizes what you copy out of the page. Follow [Access and persistence](../SKILL.md#access-and-persistence).

1. Discover **Claude in Chrome** tools (`mcp__claude-in-chrome__*`). If absent, report that X is unavailable here. Do not assume another browser has the session.
2. Use the existing session. If a login wall appears, the session has expired: log that route as a gap, take the other routes (the thread's archive copy, a search-engine view of the posts, other platforms), and tell the owner that signing in again unlocks it.
3. Open your own tab. Combine the topic with `min_faves:200 since:YYYY-MM-DD`, URL-encode the whole query, and navigate to `https://x.com/search?q=ENCODED&f=top` (`f=live` for newest). Wait about five seconds.
4. Run this in the page with the browser JavaScript tool, and save the returned JSON to a file:

```js
JSON.stringify([...document.querySelectorAll('article')].map(a => ({
  text: a.querySelector('[data-testid="tweetText"]')?.innerText || '',
  datetime: a.querySelector('time')?.getAttribute('datetime') || '',
  url: a.querySelector('a[href*="/status/"]')?.href || '',
  author: (a.querySelector('[data-testid="User-Name"] a')?.getAttribute('href') || '').replace('/', ''),
  likes: (s => { const m = s.match(/([\d.,]+)\s*([KM])?/i); return m ? Math.round(parseFloat(m[1].replace(/,/g, '')) * ({ K: 1e3, M: 1e6 }[(m[2] || '').toUpperCase()] || 1)) : 0; })(a.querySelector('[data-testid="like"], [data-testid="unlike"]')?.innerText || '')
})).filter(t => t.text))
```

5. Normalize, hash authors and score: `python scripts/read.py x --from-json FILE` (or `-` for stdin). Open relevant status permalinks for threads and replies, scroll, and repeat. Replies the page did not render are unread; label the thread partial. If the selectors return nothing, inspect the rendered page: an empty result is not a read. Like counts come from X's rounded labels (`1.2K` becomes 1200).
6. Close the tab you created. Leave the owner's other tabs alone.

On a bot check, an access denial, a 403 or a 429, wait and retry slower, read the page's own network calls for the JSON it loads, and try the mirrors and archives of [deep routes](deep-routes.md). If every route fails, finish with an X access gap, the route list and the other platforms.
