"""Count a research source log: sources read in full, per meta source, language and region.

  python scripts/source_log.py <log.md> [<log2.md> ...] [--plan "meta=10 per=10 full=100 split=china:50,west:30 must=reddit,x"] [--json]

Log format, one numbered line per source (a markdown table row with the same cells also works):
  N. meta source | URL | date | language | read=full|digest | words read | takeaway
Rules (SKILL.md "Count depth", references/counting.md):
  - A source is one unique page read in full. read=digest, a snippet or a search result counts 0.
  - The same URL twice counts once; a full line beats a digest line for the same page.
  - The meta source comes from the URL (a platform family, else the registered domain), never from the label.
  - At most `per` sources count per meta source; the rest are reported as over the cap.
  - An old log with a Tag column reads F, R, S as full and D as digest.
Exit 1 when a plan is given and not met. Python 3 standard library only; reads files, never the network.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

DEFAULT_PLAN = {"meta": 10, "per": 10, "full": 100}
FAMILY = (
    ("reddit.com", "reddit"), ("redd.it", "reddit"), ("x.com", "x"), ("twitter.com", "x"), ("t.co", "x"),
    ("youtube.com", "youtube"), ("youtu.be", "youtube"), ("bilibili.com", "bilibili"), ("b23.tv", "bilibili"),
    ("weibo.com", "weibo"), ("weibo.cn", "weibo"), ("zhihu.com", "zhihu"), ("baike.baidu.com", "baidu baike"),
    ("baidu.com", "baidu"), ("douyin.com", "douyin"), ("xiaohongshu.com", "xiaohongshu"), ("news.cn", "xinhua"),
    ("xinhuanet.com", "xinhua"), ("wikipedia.org", "wikipedia"), ("google.com", "google"), ("facebook.com", "facebook"),
    ("tiktok.com", "tiktok"), ("github.com", "github"), ("huggingface.co", "huggingface"),
    ("news.ycombinator.com", "hacker news"), ("rumble.com", "rumble"), ("instagram.com", "instagram"),
)
CHINA_META = {"bilibili", "weibo", "zhihu", "baidu baike", "baidu", "douyin", "xiaohongshu", "xinhua"}
SECOND_LEVEL = {"com", "co", "org", "net", "gov", "edu", "ac"}
LANG_NAMES = {"english": "en", "chinese": "zh", "mandarin": "zh", "serbian": "sr", "german": "de", "russian": "ru", "japanese": "ja"}
TRACKING = re.compile(r"^(utm_|fbclid|gclid|ref$|ref_src|si$|feature$|share|spm$|from$|s$|t$)", re.I)
URL = re.compile(r"https?://[^\s|)>\]]+")


def host_of(url):
    return re.sub(r"^(www|m|mobile|old|new|i|en|zh|amp)\.", "", (urlsplit(url).hostname or "").lower())


def meta_of(url, label=""):
    """The meta source of a URL: its platform family, else its registered domain; the label only when the URL has no host."""
    host = host_of(url)
    for suffix, family in FAMILY:
        if host == suffix or host.endswith("." + suffix):
            return family
    if not host:
        return re.sub(r"\s*\(.*?\)", "", label).strip().lower() or "unknown"
    parts = host.split(".")
    n = 3 if len(parts) >= 3 and parts[-2] in SECOND_LEVEL and len(parts[-1]) == 2 else 2
    return ".".join(parts[-n:])


def key_of(url):
    """One page = one key: no scheme, www, fragment, tracking or trailing slash; a Reddit thread, YouTube video and X post by id."""
    u = urlsplit(url.strip().rstrip(".,;"))
    host, path = host_of(url), u.path.rstrip("/") or "/"
    query = sorted((k, v) for k, v in parse_qsl(u.query) if not TRACKING.match(k))
    meta = meta_of(url)
    if meta == "reddit" and (m := re.search(r"/comments/(\w+)", path)):
        return f"reddit/comments/{m[1]}"
    if meta == "youtube":
        vid = dict(query).get("v") or (path.strip("/") if host == "youtu.be" else (re.search(r"/(?:shorts|embed|live)/([\w-]+)", path) or [None, None])[1])
        if vid:
            return f"youtube/{vid}"
    if meta == "x" and (m := re.search(r"/status/(\d+)", path)):
        return f"x/status/{m[1]}"
    return host + path + ("?" + "&".join(f"{k}={v}" for k, v in query) if query else "")


def region_of(url, lang, explicit=""):
    """china / serbia / west from the language and the site, or an explicit region= cell."""
    if explicit:
        return explicit.lower()
    host = host_of(url)
    if re.match(r"zh(-|$)", lang) or meta_of(url) in CHINA_META or host.endswith(".cn"):
        return "china"
    if lang in ("sr", "hr", "bs", "sh") or lang.startswith("sr-") or host.endswith(".rs"):
        return "serbia"
    return "west"


def parse_line(line):
    """One source line (numbered line or table row) -> a dict or None. Cells are read by what they hold, not by column."""
    s = line.strip()
    if not s or s[0] in "#>" or "|" not in s or not URL.search(s):
        return None
    url = URL.search(s)[0].rstrip(".,;")
    cells = [c.strip() for c in re.sub(r"^\|", "", re.sub(r"\|$", "", re.sub(r"^\s*(?:\d+[.)]|-)\s*", "", s))).split("|")]
    at = next(i for i, c in enumerate(cells) if URL.search(c))
    before, after = cells[:at], cells[at + 1:]
    label = next((c for c in before if c and not c.isdigit()), "")
    read = None
    for c in after:
        if (r := re.fullmatch(r"read\s*=\s*(full|digest)", c, re.I)):
            read = r[1].lower()
        elif re.fullmatch(r"[FRSD]", c) and read is None:
            read = "full" if c in "FRS" else "digest"          # an old Tag column
    date = next((c for c in after if re.fullmatch(r"\d{4}-\d{2}(-\d{2})?|unknown|n/a|\?", c, re.I)), "")
    lang_cell = next((c for c in after if re.fullmatch(r"[a-z]{2,3}(-[A-Za-z]+)?|english|chinese|mandarin|serbian|german|russian|japanese", c)), None)
    lang = LANG_NAMES.get(lang_cell.lower(), lang_cell.lower()) if lang_cell else "?"
    words = next((int(c.replace(",", "")) for c in after if re.fullmatch(r"\d[\d,]*", c)), None)
    region = next((r[1] for c in after if (r := re.fullmatch(r"region\s*=\s*([\w-]+)", c, re.I))), "")
    return {"url": url, "key": key_of(url), "meta": meta_of(url, label), "label": label, "date": date, "lang": lang,
            "read": read or "digest", "words": words, "region": region_of(url, lang, region)}


def parse_log(text):
    return [r for r in map(parse_line, text.splitlines()) if r]


def parse_plan(words=""):
    """Plan words 'meta=10 per=10 full=100 split=china:50,west:30 must=reddit,x' over the default."""
    plan = dict(DEFAULT_PLAN)
    w = {m[1].lower(): m[2].rstrip(",.;:") for m in re.finditer(r"(?<![\w-])([a-z][\w-]*)\s*=\s*(\S+)", str(words), re.I)}
    for k in ("meta", "per", "full", "rounds", "agents"):
        if w.get(k, "").isdigit():
            plan[k] = int(w[k])
    if w.get("split"):
        plan["split"] = {a.lower(): int(b) for a, b in re.findall(r"([a-z-]+):(\d+)", w["split"], re.I)}
    if w.get("must"):
        plan["must"] = [x.lower() for x in re.split(r"[,+]", w["must"]) if x]
    return plan


def tally(rows, plan=None):
    """Count rows (in log order): unique pages, a full line beats a digest line, at most plan per per meta source."""
    plan = plan or DEFAULT_PLAN
    unique = {}
    for r in rows:
        old = unique.get(r["key"])
        if old is None or (old["read"] == "digest" and r["read"] == "full"):
            unique[r["key"]] = r
    by_meta, counted, seen = {}, [], Counter()
    for r in unique.values():
        by_meta.setdefault(r["meta"], {"full": 0, "digest": 0, "counted": 0})[r["read"]] += 1
        if r["read"] == "full":
            seen[r["meta"]] += 1
            if seen[r["meta"]] <= plan["per"]:
                counted.append(r)
    over = {}
    for m, c in by_meta.items():
        c["counted"] = min(c["full"], plan["per"])
        if c["full"] > plan["per"]:
            over[m] = c["full"] - plan["per"]
    return {"lines": len(rows), "unique": len(unique), "counted": len(counted),
            "full": sum(r["read"] == "full" for r in unique.values()), "digest": sum(r["read"] == "digest" for r in unique.values()),
            "metas_full": sum(1 for c in by_meta.values() if c["counted"]), "by_meta": by_meta, "over": over,
            "lang": dict(Counter(r["lang"] for r in counted)), "region": dict(Counter(r["region"] for r in counted))}


def check(t, plan=None):
    """The plan against the tally -> problem lines ([] = met)."""
    plan = plan or DEFAULT_PLAN
    out = []
    if t["counted"] < plan["full"]:
        out.append(f"{t['counted']} sources read in full, plan {plan['full']} (meta={plan['meta']} per={plan['per']}); {t['digest']} digest lines count 0")
    if t["metas_full"] < plan["meta"]:
        out.append(f"{t['metas_full']} meta sources with a full read, plan {plan['meta']}")
    for region, need in (plan.get("split") or {}).items():
        if t["region"].get(region, 0) < need:
            out.append(f"region {region} has {t['region'].get(region, 0)} full sources, plan {need}")
    for m in plan.get("must") or []:
        if not t["by_meta"].get(m, {}).get("full"):
            out.append(f"mandatory meta source '{m}' has no source read in full")
    return out


def main(argv):
    args, files, plan_words = list(argv), [], None
    if "--plan" in args:
        i = args.index("--plan")
        plan_words = args[i + 1] if i + 1 < len(args) else ""
        del args[i:i + 2]
    files = [a for a in args if not a.startswith("--")]
    if not files or {"-h", "--help"} & set(args):
        print(__doc__)
        return 0 if {"-h", "--help"} & set(args) else 2
    plan = parse_plan(plan_words or "")
    t = tally([r for f in files for r in parse_log(Path(f).read_text(encoding="utf-8", errors="replace"))], plan)
    problems = check(t, plan) if plan_words is not None else []
    if "--json" in args:
        print(json.dumps({**t, "problems": problems}, indent=2, ensure_ascii=False))
    else:
        print(f"{t['lines']} source lines, {t['unique']} unique pages; counted {t['counted']} read in full (plan {plan['full']}), "
              f"{t['metas_full']} meta sources, {t['digest']} digests (0)")
        for m, c in sorted(((m, c) for m, c in t["by_meta"].items() if c["full"]), key=lambda kv: -kv[1]["counted"]):
            print(f"  {m}: {c['counted']} counted ({c['full']} full, {c['digest']} digest)")
        print(f"language: {t['lang']}  region: {t['region']}")
        for m, n in t["over"].items():
            print(f"over the cap, not counted: {m} +{n}")
        for p in problems:
            print(f"SHORT {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
