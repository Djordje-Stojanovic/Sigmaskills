"""One reader per platform. Each returns {"items": [...], "gaps": [...], "route": "..."}.

A reader that is blocked reports the status as a gap and tries only the documented fallback
for that platform. It never rotates identities, proxies or accounts.
"""
import json
import os
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import sr_core as core
from sr_core import item, strip_html

ATOM = "{http://www.w3.org/2005/Atom}"


def _q(s):
    return urllib.parse.quote(s, safe="")


def _result(items, gaps, route):
    return {"items": items, "gaps": gaps, "route": route}


def _blocked(host, resp):
    why = resp.note or ("blocked" if resp.status in (401, 403, 429) else "no data")
    return f"{host} HTTP {resp.status} ({why})" if resp.status else f"{host} unreachable ({why})"


# ============================ Reddit ============================

def reddit_plan(target, limit):
    """Return (kind, json_url, rss_url, query). kind: thread | search | top."""
    t = target.strip()
    m = re.match(r"https?://(?:www\.|old\.|new\.)?reddit\.com(/r/[^/?#]+/comments/[^?#]*)", t)
    if m:
        path = m.group(1).rstrip("/")
        return ("thread", f"https://old.reddit.com{path}.json?limit={limit * 3}&depth=3&sort=top",
                f"https://www.reddit.com{path}/.rss?limit={min(limit * 3, 100)}", "")
    m = re.match(r"https?://(?:www\.|old\.)?reddit\.com/r/([^/?#]+)/?$", t)
    sub, query = (m.group(1), "") if m else (None, t)
    if not m:
        m = re.match(r"^/?r/([A-Za-z0-9_]+)\s*(.*)$", t)
        if m:
            sub, query = m.group(1), m.group(2).strip()
    if sub and not query:
        return ("top", f"https://old.reddit.com/r/{sub}/top.json?t=month&limit={limit}",
                f"https://www.reddit.com/r/{sub}/top/.rss?t=month&limit={limit}", "")
    base = f"r/{sub}/" if sub else ""
    restrict = "&restrict_sr=1" if sub else ""
    qs = f"q={_q(query)}{restrict}&sort=top&t=year"
    return ("search", f"https://old.reddit.com/{base}search.json?{qs}&limit={limit}",
            f"https://www.reddit.com/{base}search.rss?{qs}&limit={limit}", query)


def parse_reddit_listing(doc, scope="search hit; thread not opened"):
    out = []
    for ch in doc.get("data", {}).get("children", []):
        d = ch.get("data", {})
        if ch.get("kind") != "t3":
            continue
        out.append(item("reddit", "https://www.reddit.com" + d.get("permalink", ""), d.get("title", ""),
                        d.get("selftext", ""), d.get("score"), d.get("created_utc"), d.get("author", ""),
                        "r/" + d.get("subreddit", ""), "post", scope, comments=d.get("num_comments")))
    return out


def parse_reddit_thread(doc, limit, depth=3):
    """doc = [post listing, comment listing]. Keeps the top `limit` comments by score, any depth <= `depth`."""
    posts = parse_reddit_listing(doc[0], scope="full post")
    for p in posts:
        p["scope"] = "full post"
    flat = []

    def walk(children, level):
        for ch in children:
            if ch.get("kind") != "t1" or level > depth:
                continue
            d = ch["data"]
            if d.get("body") in ("[deleted]", "[removed]"):
                continue
            sub = posts[0]["source"] if posts else "reddit"
            flat.append(item("reddit", "https://www.reddit.com" + d.get("permalink", ""), "", d.get("body", ""),
                             d.get("score"), d.get("created_utc"), d.get("author", ""), sub, "comment",
                             f"comment depth {level}", thread=posts[0]["url"] if posts else ""))
            rep = d.get("replies")
            if isinstance(rep, dict):
                walk(rep.get("data", {}).get("children", []), level + 1)

    walk(doc[1].get("data", {}).get("children", []), 1)
    flat.sort(key=lambda i: -(i["score"] or 0))
    return posts + flat[:limit]


def parse_reddit_rss(xml_text, kind):
    root = ET.fromstring(xml_text)
    out = []
    for n, e in enumerate(root.iter(ATOM + "entry")):
        link = e.find(ATOM + "link")
        url = link.get("href") if link is not None else ""
        cat = e.find(ATOM + "category")
        sub = cat.get("label") if cat is not None else ""
        if not sub:
            m = re.search(r"/r/([^/]+)/", url)
            sub = f"r/{m.group(1)}" if m else "reddit"
        author = (e.findtext(f"{ATOM}author/{ATOM}name") or "").replace("/u/", "")
        text = re.sub(r"(?s)\s*submitted by\s+/u/\S+.*$", "", strip_html(e.findtext(ATOM + "content") or ""))
        if text in ("[deleted]", "[removed]"):
            continue
        is_comment = kind == "thread" and n > 0
        scope = "comment (rss, no votes)" if is_comment else ("full post (rss)" if kind == "thread" else "search hit; rss feed excerpt")
        out.append(item("reddit", url, "" if is_comment else (e.findtext(ATOM + "title") or ""), text, None,
                        e.findtext(ATOM + "updated") or e.findtext(ATOM + "published") or "", author, sub,
                        "comment" if is_comment else "post", scope))
    return out


def parse_ddg(html_text, host="reddit.com"):
    out = []
    for m in re.finditer(r'(?s)<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?(?:class="result__snippet"[^>]*>(.*?)</a>)?', html_text):
        href = m.group(1)
        if "uddg=" in href:
            href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
        if host in href:
            out.append(item("reddit", href, strip_html(m.group(2)), strip_html(m.group(3) or ""), None, "", "",
                            "search engine", "post", "search snippet only; page not read"))
    return out


def parse_archive_html(html_text, url):
    """Archived old.reddit page: comment bodies are <div class="md">."""
    out = []
    for m in re.finditer(r'(?s)<div class="md">(.*?)</div>', html_text):
        t = strip_html(m.group(1))
        if t:
            out.append(item("reddit", url, "", t, None, "", "", "archive", "comment", "archive snapshot; votes unknown"))
    return out


def read_reddit(target, limit=10, depth=3, threads=2):
    kind, jurl, rurl, query = reddit_plan(target, limit)
    gaps = []
    items, route = [], "json"
    r = core.get(jurl)
    if r.ok:
        try:
            d = r.json()
            items = parse_reddit_thread(d, limit, depth) if kind == "thread" else parse_reddit_listing(d)
        except (ValueError, KeyError, IndexError):
            gaps.append("reddit json unparseable")
    else:
        gaps.append(_blocked("old.reddit.com json", r))
    if not items:
        route = "rss"
        r = core.get(rurl)
        if r.ok:
            try:
                items = parse_reddit_rss(r.text, kind)
            except ET.ParseError:
                gaps.append("reddit rss unparseable")
        else:
            gaps.append(_blocked("reddit.com rss", r))
    if not items:
        route = "search-engine"
        if kind == "thread":
            snap = core.get("https://archive.org/wayback/available?url=" + _q(rurl.split("/.rss")[0].replace("www.", "old.")))
            snap_url = ""
            try:
                snap_url = snap.json()["archived_snapshots"]["closest"]["url"] if snap.ok else ""
            except (ValueError, KeyError):
                pass
            if snap_url:
                route = "archive"
                page = core.get(snap_url)
                items = parse_archive_html(page.text, snap_url)[:limit] if page.ok else []
                if not page.ok:
                    gaps.append(_blocked("web.archive.org", page))
            else:
                gaps.append("no archive snapshot for this thread")
        else:
            q = "site:reddit.com " + (query or re.sub(r"https?://[^/]+/", "", target))
            r = core.get("https://html.duckduckgo.com/html/?q=" + _q(q))
            if r.ok:
                items = parse_ddg(r.text)[:limit]
            else:
                gaps.append(_blocked("duckduckgo.com", r))
    # Open the top threads of a search so comments get read, not only titles.
    if kind != "thread" and threads and route in ("json", "rss") and items:
        top = sorted([i for i in items if "/comments/" in i["url"]], key=lambda i: -(i["score"] or 0))[:threads]
        for p in top:
            sub = read_reddit(p["url"], limit=max(3, limit // 2), depth=depth, threads=0)
            items += [i for i in sub["items"] if i["kind"] == "comment"]
            gaps += sub["gaps"]
    return _result(items, gaps, route)


# ============================ Hacker News ============================

def parse_hn_search(doc):
    out = []
    for h in doc.get("hits", []):
        oid = h.get("objectID")
        link = h.get("url") or ""
        text = strip_html(h.get("story_text") or "") or (f"links to {link}" if link else "")
        out.append(item("hn", f"https://news.ycombinator.com/item?id={oid}", h.get("title") or "", text,
                        h.get("points"), h.get("created_at"), h.get("author", ""), "news.ycombinator.com", "post",
                        "story hit; comments not opened", comments=h.get("num_comments"), link=link))
    return out


def parse_hn_item(doc, limit, depth=3):
    sid = doc.get("id")
    root = f"https://news.ycombinator.com/item?id={sid}"
    out = [item("hn", root, doc.get("title") or "", strip_html(doc.get("text") or ""), doc.get("points"),
                doc.get("created_at"), doc.get("author", ""), "news.ycombinator.com", "post", "full story")]

    def walk(kids, level):
        for k in kids:
            if len(out) > limit:
                return
            if k.get("text") and level <= depth:
                out.append(item("hn", f"https://news.ycombinator.com/item?id={k.get('id')}", "", strip_html(k["text"]),
                                None, k.get("created_at"), k.get("author", ""), "news.ycombinator.com", "comment",
                                f"comment depth {level}", thread=root))
            walk(k.get("children", []), level + 1)

    walk(doc.get("children", []), 1)
    return out


def read_hn(target, limit=10, depth=3, threads=1):
    m = re.search(r"news\.ycombinator\.com/item\?id=(\d+)", target) or re.fullmatch(r"(\d+)", target.strip())
    gaps = []
    if m:
        r = core.get(f"https://hn.algolia.com/api/v1/items/{m.group(1)}")
        if not r.ok:
            return _result([], [_blocked("hn.algolia.com", r)], "algolia")
        return _result(parse_hn_item(r.json(), limit, depth), gaps, "algolia")
    r = core.get(f"https://hn.algolia.com/api/v1/search?query={_q(target)}&tags=story&hitsPerPage={limit}")
    if not r.ok:
        return _result([], [_blocked("hn.algolia.com", r)], "algolia")
    items = parse_hn_search(r.json())
    for p in sorted(items, key=lambda i: -(i["score"] or 0))[:threads]:
        sub = read_hn(p["url"], limit=max(3, limit // 2), depth=depth)
        items += [i for i in sub["items"] if i["kind"] == "comment"]
        gaps += sub["gaps"]
    return _result(items, gaps, "algolia")


# ============================ GitHub ============================

def _gh_headers():
    h = {"Accept": "application/vnd.github+json"}
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not tok:
        rc, out = core.run_cmd(["gh", "auth", "token"], timeout=10)
        tok = out.strip() if rc == 0 else ""
    if tok:
        h["Authorization"] = "Bearer " + tok  # never printed or cached: the cache key hashes headers
    return h


def parse_gh_repo(d, releases):
    rel = ", ".join(f"{r.get('tag_name')} ({(r.get('published_at') or '')[:10]})" for r in releases[:5]) or "none"
    text = (f"{d.get('description') or ''} | stars {d.get('stargazers_count')}, forks {d.get('forks_count')}, "
            f"open issues+PRs {d.get('open_issues_count')}, last push {d.get('pushed_at')}, "
            f"license {(d.get('license') or {}).get('spdx_id')}, archived {d.get('archived')} | releases: {rel}")
    return item("github", d.get("html_url", ""), d.get("full_name", ""), text, d.get("stargazers_count"),
                d.get("pushed_at"), (d.get("owner") or {}).get("login", ""), "github.com/" + d.get("full_name", ""),
                "repo", "repo metadata via API", pushed_at=d.get("pushed_at"), stars=d.get("stargazers_count"),
                open_issues=d.get("open_issues_count"))


def parse_gh_issues(doc, repo=""):
    out = []
    for i in doc.get("items", []) if isinstance(doc, dict) else doc:
        reactions = (i.get("reactions") or {}).get("total_count", 0)
        out.append(item("github", i.get("html_url", ""), i.get("title", ""), i.get("body") or "",
                        reactions + (i.get("comments") or 0), i.get("created_at"), (i.get("user") or {}).get("login", ""),
                        "github.com/" + (repo or "/".join(i.get("repository_url", "").split("/")[-2:])), "issue",
                        f"issue {i.get('state')}; {i.get('comments')} comments", state=i.get("state")))
    return out


def parse_gh_search_repos(doc):
    return [parse_gh_repo(d, []) for d in doc.get("items", [])]


def read_github(target, limit=10, depth=3, threads=0):
    h = _gh_headers()
    api = "https://api.github.com"
    t = target.strip()
    m = re.match(r"(?:https?://github\.com/)?([\w.-]+/[\w.-]+?)(?:/issues/(\d+))?(?:\.git)?/?(?:\s+(.+))?$", t)
    if not m:
        r = core.get(f"{api}/search/repositories?q={_q(t)}&sort=stars&per_page={limit}", h)
        return _result(parse_gh_search_repos(r.json()) if r.ok else [], [] if r.ok else [_blocked("api.github.com", r)], "api")
    repo, num, words = m.group(1), m.group(2), (m.group(3) or "").strip()
    gaps = []
    if num:
        r = core.get(f"{api}/repos/{repo}/issues/{num}", h)
        c = core.get(f"{api}/repos/{repo}/issues/{num}/comments?per_page={limit}", h)
        if not r.ok:
            return _result([], [_blocked("api.github.com", r)], "api")
        items = parse_gh_issues([r.json()], repo)
        if c.ok:
            for x in c.json():
                items.append(item("github", x.get("html_url", ""), "", x.get("body") or "",
                                  (x.get("reactions") or {}).get("total_count", 0), x.get("created_at"),
                                  (x.get("user") or {}).get("login", ""), "github.com/" + repo, "comment", "issue comment"))
        return _result(items, gaps, "api")
    with ThreadPoolExecutor(3) as ex:
        fr = ex.submit(core.get, f"{api}/repos/{repo}", h)
        fl = ex.submit(core.get, f"{api}/repos/{repo}/releases?per_page=5", h)
        q = f"repo:{repo} is:issue " + (words or "bug")
        fi = ex.submit(core.get, f"{api}/search/issues?q={_q(q)}&sort=reactions&per_page={limit}", h)
    r, rel, iss = fr.result(), fl.result(), fi.result()
    items = []
    if r.ok:
        items.append(parse_gh_repo(r.json(), rel.json() if rel.ok else []))
    else:
        gaps.append(_blocked("api.github.com repo", r))
    if iss.ok:
        items += parse_gh_issues(iss.json(), repo)
    else:
        gaps.append(_blocked("api.github.com issue search", iss))
    return _result(items, gaps, "api")


# ============================ Stack Overflow ============================

def parse_so(doc, kind, question_url=""):
    out = []
    for q in doc.get("items", []):
        if kind == "question":
            out.append(item("stackoverflow", q.get("link", ""), strip_html(q.get("title", "")), strip_html(q.get("body", "")),
                            q.get("score"), q.get("creation_date"), (q.get("owner") or {}).get("display_name", ""),
                            "stackoverflow.com", "question",
                            f"question; {q.get('answer_count')} answers; accepted={bool(q.get('accepted_answer_id'))}",
                            question_id=q.get("question_id")))
        else:
            out.append(item("stackoverflow", f"https://stackoverflow.com/a/{q.get('answer_id')}", "", strip_html(q.get("body", "")),
                            q.get("score"), q.get("creation_date"), (q.get("owner") or {}).get("display_name", ""),
                            "stackoverflow.com", "answer", "accepted answer" if q.get("is_accepted") else "answer", thread=question_url))
    return out


def read_stackoverflow(target, limit=10, depth=3, threads=3):
    base = "https://api.stackexchange.com/2.3"
    m = re.search(r"stackoverflow\.com/questions/(\d+)", target)
    if m:
        qid = m.group(1)
        qs = [core.get(f"{base}/questions/{qid}?site=stackoverflow&filter=withbody")]
    else:
        qs = [core.get(f"{base}/search/advanced?order=desc&sort=votes&q={_q(target)}&site=stackoverflow&pagesize={limit}&filter=withbody")]
    if not qs[0].ok:
        return _result([], [_blocked("api.stackexchange.com", qs[0])], "api")
    items = parse_so(qs[0].json(), "question")
    gaps = []
    top = sorted(items, key=lambda i: -(i["score"] or 0))[: (1 if m else threads)]
    with ThreadPoolExecutor(3) as ex:
        futs = [(p, ex.submit(core.get, f"{base}/questions/{p['question_id']}/answers?order=desc&sort=votes&site=stackoverflow&pagesize=3&filter=withbody")) for p in top]
    for p, f in futs:
        a = f.result()
        if a.ok:
            items += parse_so(a.json(), "answer", p["url"])
        else:
            gaps.append(_blocked("api.stackexchange.com answers", a))
    return _result(items, gaps, "api")


# ============================ YouTube comments ============================

def parse_yt(info, limit):
    vid = info.get("webpage_url") or f"https://www.youtube.com/watch?v={info.get('id')}"
    chan = "youtube:" + (info.get("channel") or info.get("uploader") or "unknown")
    out = [item("youtube", vid, info.get("title", ""), info.get("description") or "", info.get("like_count"),
                info.get("upload_date"), info.get("channel") or "", chan, "video", "metadata + description",
                views=info.get("view_count"))]
    cs = [c for c in info.get("comments") or [] if c.get("text")]
    cs.sort(key=lambda c: -(c.get("like_count") or 0))
    for c in cs[:limit]:
        out.append(item("youtube", f"{vid}&lc={c.get('id')}", "", c["text"], c.get("like_count"), c.get("timestamp"),
                        c.get("author", ""), chan, "comment", "reply" if c.get("parent") not in (None, "root") else "top-level comment",
                        thread=vid))
    return out


def read_youtube(target, limit=10, depth=3, threads=0):
    rc, _ = core.run_cmd(["yt-dlp", "--version"], timeout=20)
    if rc != 0:
        return _result([], ["yt-dlp not installed or not on PATH (YouTube comments need it)"], "yt-dlp")
    src = target if re.match(r"https?://", target) else f"ytsearch1:{target}"
    args = ["yt-dlp", "--skip-download", "--write-comments", "--dump-single-json", "--no-warnings", "--no-playlist",
            "--extractor-args", f"youtube:max_comments={limit * 5},all,0,0;comment_sort=top", src]
    rc, out = core.run_cmd(args)
    if rc != 0 or not out.strip():
        return _result([], [f"yt-dlp failed (exit {rc}); video blocked, private or comments off"], "yt-dlp")
    info = json.loads(out)
    if info.get("entries"):
        info = info["entries"][0]
    return _result(parse_yt(info, limit), [], "yt-dlp")


# ============================ X (signed-in Chrome, read-only) ============================

X_GAP = ("X is read only through the owner's signed-in Chrome: run the JS in references/x.md in a Chrome tab, "
         "save its JSON, then `read.py x --from-json FILE`")


def parse_x_dump(doc):
    """doc = list of {text, datetime, url, author?, likes?} from the Chrome snippet."""
    out = []
    for t in doc if isinstance(doc, list) else doc.get("posts", []):
        url = t.get("url") or ""
        out.append(item("x", url, "", t.get("text", ""), t.get("likes"), t.get("datetime"), t.get("author", ""),
                        "x.com", "post", "post text as rendered in Chrome; replies only if listed"))
    return out


def read_x(target, limit=10, depth=3, threads=0, from_json=None):
    if not from_json:
        return _result([], [X_GAP], "chrome")
    if from_json == "-":
        raw = sys.stdin.read()
    else:
        with open(from_json, encoding="utf-8") as f:
            raw = f.read()
    return _result(parse_x_dump(json.loads(raw))[:limit], [], "chrome")


READERS = {"reddit": read_reddit, "hn": read_hn, "github": read_github, "stackoverflow": read_stackoverflow,
           "youtube": read_youtube, "x": read_x}
ALIASES = {"so": "stackoverflow", "yt": "youtube", "hackernews": "hn", "twitter": "x", "gh": "github"}

# One fixed query per platform for the self-test; pass = at least N items parsed.
SELFTEST = {"reddit": ("r/programming python", 3), "hn": ("sqlite", 3), "github": ("yt-dlp/yt-dlp", 3),
            "stackoverflow": ("python asyncio", 3), "youtube": ("https://www.youtube.com/watch?v=jNQXAC9IVRw", 2)}
