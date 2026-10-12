"""Shared plumbing for SigmaResearch readers: HTTP, cache, rate limits, items, scoring.

Python stdlib only. Read-only. A blocked host is reported, never bypassed.
"""
import gzip
import hashlib
import html
import json
import math
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "sigmaresearch/2.0 (read-only research script; +https://github.com/Djordje-Stojanovic/Sigmaskills)"
CACHE_TTL = 24 * 3600
# Minimum seconds between two requests to one host (shared by all threads).
HOST_GAP = {"reddit.com": 6.0, "duckduckgo.com": 3.0, "archive.org": 1.0, "stackexchange.com": 0.5}
DEFAULT_GAP = 0.25
MAX_TRIES = 3  # 429 only: waits 2 s, 4 s (or Retry-After, capped), then gives up
MAX_WAIT = 20.0

_lock = threading.Lock()
_next_ok = {}
USE_CACHE = True


class Resp:
    def __init__(self, status, text="", url="", cached=False, note=""):
        self.status, self.text, self.url, self.cached, self.note = status, text, url, cached, note

    @property
    def ok(self):
        return self.status == 200

    def json(self):
        return json.loads(self.text)


def cache_dir():
    return Path(os.environ.get("SIGMARESEARCH_CACHE") or Path.home() / ".cache" / "sigmaresearch")


def _cache_path(url, headers):
    key = url + "\n" + json.dumps(sorted((headers or {}).items()))
    return cache_dir() / (hashlib.sha256(key.encode()).hexdigest() + ".json")


def _host_key(url):
    host = urllib.parse.urlsplit(url).hostname or ""
    for k in HOST_GAP:
        if host == k or host.endswith("." + k):
            return k
    return host


def _wait_turn(url):
    key = _host_key(url)
    gap = HOST_GAP.get(key, DEFAULT_GAP)
    with _lock:
        now = time.monotonic()
        at = max(now, _next_ok.get(key, 0.0))
        _next_ok[key] = at + gap
    if at > now:
        sleep(at - now)


def sleep(seconds):  # one seam so tests can skip real waiting
    time.sleep(seconds)


def _retry_wait(resp, attempt):
    try:
        wait = float(resp.note)
    except ValueError:
        wait = 0.0
    return min(MAX_WAIT, wait if wait > 0 else 2.0 ** (attempt + 1))


def get(url, headers=None, use_cache=True):
    """GET with 24 h cache, per-host spacing and bounded 429 backoff. Never follows a login redirect."""
    headers = dict(headers or {})
    path = _cache_path(url, headers)
    if USE_CACHE and use_cache:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - doc["t"] < CACHE_TTL:
                return Resp(200, doc["body"], url, cached=True)
        except (OSError, ValueError, KeyError):
            pass
    req_headers = {"User-Agent": UA, "Accept-Encoding": "gzip", **headers}
    resp = Resp(0, note="no response")
    for attempt in range(MAX_TRIES):
        _wait_turn(url)
        resp = _once(url, req_headers)
        if resp.status != 429 or attempt == MAX_TRIES - 1:
            break
        sleep(_retry_wait(resp, attempt))
    if resp.ok and USE_CACHE and use_cache:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"t": time.time(), "body": resp.text}), encoding="utf-8")
        except OSError:
            pass
    return resp


def _once(url, headers, hops=0):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(urllib.request.Request(url, headers=headers), timeout=30) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            return Resp(r.status, raw.decode("utf-8", "replace"), url)
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location", "")
        if e.code in (301, 302, 303, 307, 308) and loc:
            if re.search(r"/(login|account/login)\b", loc):
                return Resp(401, url=url, note="login wall")
            if hops < 3:
                return _once(urllib.parse.urljoin(url, loc), headers, hops + 1)
        return Resp(e.code, url=url, note=e.headers.get("Retry-After", "") or "")
    except Exception as e:  # network down, timeout, DNS
        return Resp(0, url=url, note=type(e).__name__)


def run_cmd(args, timeout=180):
    """Run a local CLI (yt-dlp, gh). Returns (returncode, stdout). Seam for tests."""
    try:
        p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, p.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""


# ---------- text helpers ----------

def strip_html(s):
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s or "")
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"\n\s*\n+", "\n", s)).strip()


def author_hash(name):
    return hashlib.sha1(("sr:" + name).encode()).hexdigest()[:10] if name else ""


def iso(ts):
    """Epoch seconds, YYYYMMDD or ISO string to an ISO-8601 UTC string; '' if unknown."""
    if ts in (None, ""):
        return ""
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    s = str(ts).strip()
    if re.fullmatch(r"\d{8}", s):
        return f"{s[:4]}-{s[4:6]}-{s[6:]}T00:00:00Z"
    return s.replace("+00:00", "Z")


def parse_dt(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, AttributeError):
        return None


def quote(text, n=240):
    t = re.sub(r"\s+", " ", text or "").strip()
    if len(t) <= n:
        return t
    cut = t[:n]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return cut[: end + 1] if end > n // 2 else cut.rsplit(" ", 1)[0] + " ..."


def item(platform, url, title="", text="", score=None, date="", author="", source="", kind="post", scope="", **extra):
    text = (text or "").strip()
    return {
        "platform": platform, "source": source or platform, "url": url, "title": (title or "").strip(),
        "text": text, "score": score, "date": iso(date), "author": author_hash(author), "kind": kind,
        "scope": scope, "quote": quote(text or title), **extra,
    }


# ---------- scoring ----------

VOTE_CAP = {"reddit": 5000, "hn": 1000, "github": 50000, "stackoverflow": 2000, "youtube": 1000, "x": 5000}


def score_items(items, now=None):
    """Add rank in 0..1: 0.40 votes (log scale), 0.35 recency (1-year half-life), 0.25 independence.
    Independence falls when one author repeats in the set and is 0 for a repeated text."""
    now = now or datetime.now(timezone.utc)
    by_author, seen = {}, set()
    for it in items:
        if it["author"]:
            k = (it["platform"], it["author"])
            by_author[k] = by_author.get(k, 0) + 1
    for it in items:
        d = parse_dt(it["date"])
        recency = 0.5 if d is None else 0.5 ** (max((now - d).total_seconds(), 0) / 86400 / 365)
        sc = it["score"]
        votes = 0.3 if sc is None else min(1.0, math.log1p(max(sc, 0)) / math.log1p(VOTE_CAP.get(it["platform"], 1000)))
        indep = 1.0 / by_author[(it["platform"], it["author"])] if it["author"] else 0.7
        sig = re.sub(r"\W+", "", it["text"].lower())[:200]
        if sig and sig in seen:
            indep = 0.0
        seen.add(sig)
        it["rank"] = round(0.40 * votes + 0.35 * recency + 0.25 * indep, 3)
    return sorted(items, key=lambda i: -i["rank"])


def unique_sources(items):
    """Distinct (platform, source) pairs: the unit of the 10+ sources rule."""
    return len({(i["platform"], i["source"]) for i in items})
