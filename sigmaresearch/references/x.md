# X in Chrome

X is read only through the owner's already signed-in Chrome. The script never contacts X; it normalizes what you copy out of the page. Follow [access boundaries](../SKILL.md#access-boundaries).

1. Discover **Claude in Chrome** tools (`mcp__claude-in-chrome__*`). If absent, report that X is unavailable here. Do not assume another browser has the session.
2. Use the existing session only. If a login wall appears, stop: the owner must restore the session. The agent never signs in or handles credentials.
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

Stop on a bot check, access denial, 403 or 429. Do not replay requests, extract tokens, call private endpoints or try mirrors. If nothing works, finish with an X access gap and the other platforms.
