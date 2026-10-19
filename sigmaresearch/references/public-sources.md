# Public research sources

Follow [Access and persistence](../SKILL.md#access-and-persistence). A missing tool is a row on the route list; installing a tool the owner's machines can run (any GitHub project is allowed) is often the fastest route. Each reader below is `python scripts/read.py <platform> "<query | URL>"`.

## Hacker News (`hn`)

Algolia API. A query returns top stories; the top `--threads` (default 1) are opened with comments to `--depth`. An item URL or id returns the story and its comment tree. Comments carry no points; the tree keeps HN's own ranking order. Scope says "story hit; comments not opened" for the rest.

## GitHub (`github`)

`owner/repo`, a repo URL or an issue URL, or a topic query (repo search by stars). A repo read returns stars, forks, open issues plus PRs, last push, licence, archived flag and the last five release dates, then the most-reacted issues matching `bug` or the words after the repo (`github "yt-dlp/yt-dlp download fails"`). It uses `GITHUB_TOKEN` or `gh auth token` when present, for rate limit only; the token is never printed or cached. Cite a commit or tag for source behavior. The reader only reads; code search, issue search and commit search are in [deep routes](deep-routes.md).

## Stack Overflow (`stackoverflow`)

Search API sorted by votes, then the top three answers of the top three questions. A question URL returns that question and its top answers. Check answer dates; old accepted answers go stale.

## YouTube (`youtube`)

Needs `yt-dlp` on PATH. Reads title, description and the top comments by likes for a video URL (`--limit N`), without downloading the video. A non-URL query reads the first search hit. Private, removed or comment-off videos come back as a gap.

## Hugging Face

No reader. Read the public model or dataset page and its discussions with the host's fetch tools; the [model card](https://huggingface.co/docs/hub/en/model-cards) states intended use and limits. Record the revision when a claim depends on a file. Downloads and likes do not prove accuracy. For gated or private repos, read the public model card, the discussions, the file list and a mirror, and report what stays unread.

## Self-test

`python scripts/read.py selftest` uses one fixed query per platform and bypasses the cache. PASS means enough items parsed. BLOCKED means the host refused, which is a result, not a bug. FAIL means a reader or its parser is broken.
