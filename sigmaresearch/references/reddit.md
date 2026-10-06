# Reddit RSS

Adapted from the owner's `research-access.md` recipe, tested 2026-10-04. That is historical evidence, not a fresh availability check. Follow the access boundaries in [SigmaResearch](../SKILL.md#access-boundaries); the original recipe's 429 retry is intentionally omitted.

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

Write temporary response files in a task-owned temporary directory. The user agent is ordinary request metadata, not a way to defeat a block. No automatic retries or redirect following: inspect a redirect before deciding whether it still points to a public feed. A transport error, non-feed body or unexpected status is an access gap. On 403/429, stop all Reddit requests for this run.

Feeds use Atom XML: parse with its namespace `http://www.w3.org/2005/Atom`. Each `entry` has a link, date fields and HTML content. Decode HTML entities and strip markup while preserving text and links; never execute the HTML. Keep the canonical thread/comment URL beside extracted evidence.

The feed limit is a requested cap, not a guarantee of the whole post plus 24 comments. Deleted, omitted or truncated material stays unknown. Record the entries actually read and whether replies are partial. Do not switch to `.json`, `api.reddit.com`, mirrors or archives after a block.
