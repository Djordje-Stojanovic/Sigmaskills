# Reddit RSS

Adapted from the owner's `research-access.md` recipe, tested 2026-10-04 and 2026-10-15. That is historical evidence, not a fresh availability check. Follow the access boundaries in [SigmaResearch](../SKILL.md#access-boundaries) and the [access ladder](access-ladder.md).

**Rung 1, JSON:** add `.json?limit=500` to a thread URL (`https://www.reddit.com/r/SUB/comments/ID/slug/.json?limit=500`; also on `old.reddit.com`). It returns the post and every comment. Some networks get 403 here: take the RSS feeds below, which are rung 2.

Use `curl` for public feeds, without cookies or login. On PowerShell, call `curl.exe` to avoid the `curl` alias. Keep requests sequential and wait about **10 seconds between requests**, including requests across different subreddits. Do not parallelize them.

Choose topic-relevant subreddits. Replace `SUB`, `QUERY` and `ID` in these URL templates; URL-encode the query as one parameter value:

| Purpose | URL |
|---|---|
| Top posts this month | `https://www.reddit.com/r/SUB/top/.rss?t=month` |
| Search one subreddit | `https://www.reddit.com/r/SUB/search.rss?q=QUERY&restrict_sr=1&sort=top&t=year` |
| Thread and comments | `https://www.reddit.com/r/SUB/comments/ID/.rss?limit=25` |

Use `t=year` for a wider window when appropriate. Prefer subreddit search over site-wide search, which throttled more often in the source test. Read the comment feed of selected relevant threads, not only ranked titles.

Run **one request**, then inspect its status and body before another. For example, after filling in the URL:

```powershell
$researchUrl = 'https://www.reddit.com/r/SUB/top/.rss?t=month'
curl.exe --silent --show-error --max-time 30 --dump-header reddit-headers.txt --output reddit-feed.xml --write-out '%{http_code}' --user-agent 'Mozilla/5.0' $researchUrl
# Only after a successful feed response, before the next request:
Start-Sleep -Seconds 10
```

```bash
research_url='https://www.reddit.com/r/SUB/top/.rss?t=month'
curl --silent --show-error --max-time 30 --dump-header reddit-headers.txt --output reddit-feed.xml --write-out '%{http_code}' --user-agent 'Mozilla/5.0' "$research_url"
# Only after a successful feed response, before the next request:
sleep 10
```

Write temporary response files in a task-owned temporary directory. The user agent is ordinary request metadata, not a way to defeat a block. No automatic retries (one manual retry after a 429 wait) or redirect following: inspect a redirect before deciding whether it still points to a public feed. A transport error, non-feed body or unexpected status is an access gap. On 429 wait 45 to 60 seconds and retry that URL once. On 403 or a second 429, stop that route and take the next rung of the ladder.

Feeds use Atom XML: parse with its namespace `http://www.w3.org/2005/Atom`. Each `entry` has a link, date fields and HTML content. Decode HTML entities and strip markup while preserving text and links; never execute the HTML. Keep the canonical thread/comment URL beside extracted evidence.

`limit=100` returned a post with 95 comments on 2026-10-15; `limit=25` returns about 24. The feed limit is a requested cap, not a guarantee of the whole post. Deleted, omitted or truncated material stays unknown. Record the entries actually read and whether replies are partial.
