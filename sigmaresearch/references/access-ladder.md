# Access ladder

Walk this ladder for every URL you need to read in full. When a rung is blocked, take the next and log which rung worked. Do not report a platform as dead before the last rung. Follow the [access boundaries](../SKILL.md#access-boundaries). The tests below were run on 2026-10-15 from one home connection; that is historical evidence, not a live check.

| Rung | Route | Example | Blocked means |
|---|---|---|---|
| 1 | Public JSON endpoint | Reddit: add `.json?limit=500` to the thread URL (post and every comment); also on `old.reddit.com` | 403 or 429: next rung |
| 2 | RSS or Atom feed | Reddit: add `.rss?limit=100` to the thread URL (post and about 95 comments); most blogs, news sites and subreddits publish a feed | 429: wait, retry once; then next rung |
| 3 | Old, lite or mobile HTML | `curl -s -L -A "$UA" URL`, then strip the tags; article pages of most news sites | an empty shell page: next rung |
| 4 | Official API or free tier that needs no login | Hacker News Firebase API, GitHub through an existing `gh`, a site's public JSON list | a key or login is needed: next rung |
| 5 | Archive mirror | `https://web.archive.org/web/<URL>` for a public page that is down or removed | no copy: next rung. Never use a mirror to get past a paywall |
| 6 | The host's own browser tool | its read-page or page-text call; it renders pages that plain requests cannot | the tool refuses the site: next rung |
| 7 | The owner's browser session | Claude in Chrome, read only: [X in Chrome](x.md) | extension missing or session gone: log the gap |
| 8 | Video sites | subtitles, then audio and speech-to-text: [video sites](#video-sites) | the site refuses the audio: log the gap |

`UA` is an ordinary browser user agent, for example `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36`. It is plain request metadata, never a disguise. On Windows PowerShell call `curl.exe`, because `curl` is an alias.

## Rate limits

Send requests one at a time per site, about 10 seconds apart. On 429 wait 45 to 60 seconds and retry that URL once. If several agents share one IP address, they share the limit: that is the usual cause of a 429. A second 429, a 403, a login wall or a bot check ends that rung for that URL. Never solve a CAPTCHA, log in or use a cookie or token.

## What the 2026-10-15 test showed

- **Reddit:** `.json` returned 403 ("blocked by network security") from that IP, and `old.reddit.com` answered with HTML. The thread `.rss?limit=100` returned 429 once, then 200 after a 45 second wait: 96 entries, the post and 95 comments. Some other networks serve `.json` fine, so always try rung 1 first.
- **A host browser tool** refused `reddit.com` by its own safety rule. Claude in Chrome was not connected.
- **Bilibili:** its public popular-list API answered without a login; search answered 412; subtitles need a login, so a Bilibili video went to the audio rung.
- **A Chinese state news site:** the home page returned 200 with article links; an article page read with `curl` and tag stripping gave the full body.

## Pages in another language

Fetch the original page; do not search for an English copy. Translate inline in your notes. Keep the original quote and the URL in the takeaway, so the user can check it. State the page language in the source log. Chinese, Serbian, German and other local sites are first-class sources: some stories exist only there.

## Video sites

Subtitles first, with no login. With `yt-dlp` (an existing install; do not install software for this):

```bash
yt-dlp --skip-download --write-subs --write-auto-subs --sub-langs "zh.*,zh" -o "%(id)s" URL
```

Clean the subtitle file to plain text (no timings, no repeated rolling lines). No subtitles, or the site wants a login for them (Bilibili does): take the audio only and run a local speech-to-text tool that is already installed:

```bash
yt-dlp -f ba -x --audio-format wav -o "%(id)s.%(ext)s" URL
whisper VIDEO_ID.wav --language zh --model small --output_format txt
```

`faster-whisper` works the same way. Pass the video's language. Count the words of the transcript (for Chinese, Japanese and Korean count characters) and write that number in the source log. A video counts as read in full only through its full subtitles or full transcript, never through its title, description or comments alone. If the audio download is refused, or no speech-to-text tool exists, log the gap.
