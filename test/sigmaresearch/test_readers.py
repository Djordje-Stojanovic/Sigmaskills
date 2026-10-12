"""Unit tests for the SigmaResearch readers. No network: every response is a recorded fixture.

Run: python -m unittest discover -s test/sigmaresearch   (from the repo root)
Optional live smoke: SIGMARESEARCH_LIVE=1 python -m unittest discover -s test/sigmaresearch
"""
import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
FX = HERE / "fixtures"
sys.path.insert(0, str(HERE.parent.parent / "sigmaresearch" / "scripts"))
import read  # noqa: E402
import sr_core as core  # noqa: E402
import sr_readers as rd  # noqa: E402

INDEX = {u: (FX / n).read_text(encoding="utf-8") for u, n in json.loads((FX / "index.json").read_text()).items()}
R_SEARCH = "https://www.reddit.com/r/programming/search.rss?q=python&restrict_sr=1&sort=top&t=year&limit=3"
R_SEARCH_JSON = "https://old.reddit.com/r/programming/search.json?q=python&restrict_sr=1&sort=top&t=year&limit=3"
INDEX[R_SEARCH] = (FX / "reddit_search.rss.xml").read_text(encoding="utf-8")
THREAD = "https://www.reddit.com/r/programming/comments/1x1pypx/python_release_python_3150/"
INDEX[THREAD.rstrip("/") + ".rss?limit=9"] = (FX / "reddit_thread.rss.xml").read_text(encoding="utf-8")


class Fake:
    """Replaces core.get / core.run_cmd. `blocked` maps a URL prefix to a status."""

    def __init__(self, extra=None, blocked=None):
        self.pages, self.blocked, self.calls = {**INDEX, **(extra or {})}, blocked or {}, []

    def get(self, url, headers=None, use_cache=True):
        self.calls.append(url)
        for prefix, status in self.blocked.items():
            if url.startswith(prefix):
                return core.Resp(status, url=url, note="login wall" if status == 401 else "")
        if url in self.pages:
            return core.Resp(200, self.pages[url], url)
        return core.Resp(404, url=url)


class Base(unittest.TestCase):
    def setUp(self):
        self._get, self._run, self._sleep = core.get, core.run_cmd, core.sleep
        os.environ["GITHUB_TOKEN"] = "test-token-not-real"
        core.run_cmd = lambda *a, **k: (127, "")

    def tearDown(self):
        core.get, core.run_cmd, core.sleep = self._get, self._run, self._sleep

    def use(self, fake):
        core.get = fake.get
        return fake


class TestReddit(Base):
    def test_rss_search_parsed_and_cleaned(self):
        items = rd.parse_reddit_rss(INDEX[R_SEARCH], "search")
        self.assertEqual(len(items), 3)
        self.assertTrue(all(i["platform"] == "reddit" and i["source"] == "r/programming" for i in items))
        self.assertNotIn("submitted by", " ".join(i["text"] for i in items))

    def test_rss_thread_post_then_comments(self):
        items = rd.parse_reddit_rss(INDEX[THREAD.rstrip("/") + ".rss?limit=9"], "thread")
        self.assertEqual(items[0]["kind"], "post")
        self.assertTrue(all(i["kind"] == "comment" for i in items[1:]))
        self.assertGreaterEqual(len(items), 5)

    def test_json_thread_top_by_score_depth_and_deleted(self):
        doc = json.loads((FX / "reddit_thread.json").read_text(encoding="utf-8"))
        items = rd.parse_reddit_thread(doc, limit=2, depth=3)
        self.assertEqual(items[0]["kind"], "post")
        comments = items[1:]
        self.assertEqual([c["text"] for c in comments], ["Not on Windows.", "Yes, by 2x on my machine."])
        self.assertEqual(comments[0]["scope"], "comment depth 2")
        shallow = rd.parse_reddit_thread(doc, limit=9, depth=1)
        self.assertNotIn("Not on Windows.", [c["text"] for c in shallow])
        self.assertNotIn("[deleted]", [c["text"] for c in items + shallow])

    def test_json_blocked_falls_back_to_rss(self):
        f = self.use(Fake(blocked={"https://old.reddit.com": 401}))
        r = rd.read_reddit("r/programming python", limit=3, threads=0)
        self.assertEqual(r["route"], "rss")
        self.assertEqual(len(r["items"]), 3)
        self.assertIn("401", r["gaps"][0])
        self.assertIn(R_SEARCH, f.calls)

    def test_all_reddit_routes_blocked_uses_search_engine_snippets(self):
        self.use(Fake(blocked={"https://old.reddit.com": 401, "https://www.reddit.com": 429}))
        r = rd.read_reddit("r/programming python", limit=3, threads=0)
        self.assertEqual(r["route"], "search-engine")
        self.assertTrue(r["items"])
        self.assertTrue(all("snippet only" in i["scope"] for i in r["items"]))
        self.assertEqual(len(r["gaps"]), 2)

    def test_blocked_with_no_fallback_reports_gaps_only(self):
        self.use(Fake(blocked={"https://old.reddit.com": 403, "https://www.reddit.com": 403, "https://html.duckduckgo.com": 403}))
        r = rd.read_reddit("r/programming python", limit=3, threads=0)
        self.assertEqual(r["items"], [])
        self.assertEqual(len(r["gaps"]), 3)

    def test_plan_shapes(self):
        self.assertEqual(rd.reddit_plan(THREAD, 5)[0], "thread")
        self.assertEqual(rd.reddit_plan("https://www.reddit.com/r/python/", 5)[0], "top")
        k, j, rss, q = rd.reddit_plan("best sqlite gui", 5)
        self.assertEqual((k, q), ("search", "best sqlite gui"))
        self.assertIn("old.reddit.com/search.json?q=best%20sqlite%20gui", j)

    def test_opens_top_threads_for_comments(self):
        f = self.use(Fake(blocked={"https://old.reddit.com": 401}))
        first = rd.parse_reddit_rss(INDEX[R_SEARCH], "search")[0]["url"]  # threads sort ties by feed order
        f.pages[first.rstrip("/") + ".rss?limit=9"] = INDEX[THREAD.rstrip("/") + ".rss?limit=9"]
        r = rd.read_reddit("r/programming python", limit=3, threads=1)
        self.assertTrue(any(i["kind"] == "comment" for i in r["items"]))

    def test_query_terms_phrase_and_hyphen(self):
        self.assertEqual(rd.query_terms('social-auto-upload "tiktok uploader"'), ["tiktok uploader", "social auto upload"])
        self.assertEqual(rd.query_terms("r/x"), ["r x"])

    def test_relevance_filter_drops_offtopic_and_counts(self):
        items = rd.parse_reddit_rss((FX / "reddit_offtopic_search.rss.xml").read_text(encoding="utf-8"), "search")
        self.assertEqual(len(items), 6)  # recorded live: r/onlyfansadvice, r/SideHustleGold ... none mention the query
        kept, dropped = rd.keep_relevant(items, "social-auto-upload tiktok")
        self.assertEqual((kept, dropped), ([], 6))

    def test_relevance_keeps_hits_with_all_terms_or_phrase(self):
        a = core.item("reddit", "u1", "Social Auto Upload for TikTok", "")
        b = core.item("reddit", "u2", "Side hustles", "we use social_auto_upload and tiktok daily")
        c = core.item("reddit", "u3", "Side hustles", "only tiktok here")
        kept, dropped = rd.keep_relevant([a, b, c], "social-auto-upload tiktok")
        self.assertEqual((kept, dropped), ([a, b], 1))
        self.assertEqual(rd.keep_relevant([a, c], '"auto upload for tiktok"')[1], 1)

    def test_read_reddit_search_reports_dropped_and_opens_no_offtopic_threads(self):
        url = "https://www.reddit.com/search.rss?q=social-auto-upload%20tiktok&sort=top&t=year&limit=8"
        f = self.use(Fake(extra={url: (FX / "reddit_offtopic_search.rss.xml").read_text(encoding="utf-8")},
                          blocked={"https://old.reddit.com": 401, "https://html.duckduckgo.com": 403}))
        r = rd.read_reddit("social-auto-upload tiktok", limit=8, threads=2)
        self.assertEqual(r["items"], [])
        self.assertEqual(r["dropped"], 6)
        self.assertTrue(any("dropped 6" in g for g in r["gaps"]))
        self.assertFalse(any("/comments/" in c for c in f.calls))

    def test_thread_reads_dot_rss_form(self):
        f = self.use(Fake(blocked={"https://old.reddit.com": 401}))
        r = rd.read_reddit(THREAD, limit=3, threads=0)
        self.assertEqual(r["route"], "rss")
        self.assertIn(THREAD.rstrip("/") + ".rss?limit=9", f.calls)
        self.assertTrue(any(i["kind"] == "comment" for i in r["items"]))
        self.assertFalse(any("BLOCKED" in g for g in r["gaps"]))

    def test_thread_with_nothing_loading_says_blocked(self):
        self.use(Fake(blocked={"https://old.reddit.com": 401, "https://www.reddit.com": 429, "https://archive.org": 403}))
        r = rd.read_reddit(THREAD, limit=3, threads=0)
        self.assertEqual(r["items"], [])
        self.assertTrue(any(g.startswith("BLOCKED") for g in r["gaps"]))


class TestPlatforms(Base):
    def test_hn_search_and_thread(self):
        self.use(Fake())
        r = rd.read_hn("sqlite", limit=3, threads=1)
        posts = [i for i in r["items"] if i["kind"] == "post"]
        self.assertEqual(len(posts), 3)
        self.assertTrue(all(p["url"].startswith("https://news.ycombinator.com/item?id=") for p in posts))
        self.assertTrue(any(i["kind"] == "comment" for i in r["items"]))

    def test_hn_item_url_depth(self):
        self.use(Fake())
        r = rd.read_hn("https://news.ycombinator.com/item?id=27016630", limit=50, depth=1)
        self.assertEqual(r["items"][0]["kind"], "post")
        self.assertTrue(all(i["scope"] == "comment depth 1" for i in r["items"][1:]))

    def test_github_repo(self):
        self.use(Fake())
        r = rd.read_github("yt-dlp/yt-dlp", limit=3)
        repo = r["items"][0]
        self.assertEqual(repo["kind"], "repo")
        self.assertIn("last push", repo["text"])
        self.assertIn("releases:", repo["text"])
        self.assertGreater(repo["stars"], 1000)
        self.assertTrue(any(i["kind"] == "issue" for i in r["items"]))
        self.assertEqual(r["gaps"], [])

    def test_github_token_never_in_output_or_cache_key(self):
        self.use(Fake())
        r = rd.read_github("yt-dlp/yt-dlp", limit=3)
        self.assertNotIn("test-token-not-real", json.dumps(r))

    def test_stackoverflow_question_and_answers(self):
        self.use(Fake())
        r = rd.read_stackoverflow("python asyncio", limit=3, threads=1)
        kinds = [i["kind"] for i in r["items"]]
        self.assertEqual(kinds.count("question"), 3)
        self.assertIn("answer", kinds)

    def test_youtube_comments_sorted_by_likes(self):
        info = json.loads((FX / "youtube_info.json").read_text(encoding="utf-8"))
        calls = []

        def run(args, timeout=180):
            calls.append(args)
            return (0, "yt-dlp 1") if args[1] == "--version" else (0, json.dumps(info))

        core.run_cmd = run
        r = rd.read_youtube("https://www.youtube.com/watch?v=jNQXAC9IVRw", limit=4)
        self.assertEqual(r["items"][0]["kind"], "video")
        likes = [i["score"] or 0 for i in r["items"][1:]]
        self.assertEqual(likes, sorted(likes, reverse=True))
        self.assertEqual(len(likes), 4)
        self.assertIn("--skip-download", calls[1])
        self.assertIn("--write-comments", calls[1])

    def test_youtube_missing_tool_is_a_gap(self):
        r = rd.read_youtube("anything")
        self.assertEqual(r["items"], [])
        self.assertIn("yt-dlp not installed", r["gaps"][0])

    def test_x_gap_without_dump_and_parse_with_dump(self):
        self.assertIn("Chrome", rd.read_x("topic")["gaps"][0])
        r = rd.read_x("topic", from_json=str(FX / "x_dump.json"))
        self.assertEqual([i["score"] for i in r["items"]], [120, 4])
        self.assertEqual(r["route"], "chrome")


class TestCore(Base):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SIGMARESEARCH_CACHE"] = self.tmp.name
        self._once, self._gap = core._once, dict(core.HOST_GAP)
        core.HOST_GAP.clear()
        core.DEFAULT_GAP = 0.0
        core._next_ok.clear()
        self.sleeps = []
        core.sleep = self.sleeps.append

    def tearDown(self):
        core._once = self._once
        core.HOST_GAP.update(self._gap)
        core.DEFAULT_GAP = 0.25
        os.environ.pop("SIGMARESEARCH_CACHE", None)
        self.tmp.cleanup()
        super().tearDown()

    def script(self, *resps):
        seq = list(resps)
        calls = []

        def once(url, headers, hops=0):
            calls.append(url)
            return seq.pop(0)

        core._once = once
        return calls

    def test_429_backoff_then_success(self):
        calls = self.script(core.Resp(429, note=""), core.Resp(429, note=""), core.Resp(200, "ok"))
        r = core.get("https://example.test/a")
        self.assertTrue(r.ok)
        self.assertEqual(len(calls), 3)
        self.assertEqual(self.sleeps, [2.0, 4.0])

    def test_429_honors_retry_after_and_caps(self):
        self.script(core.Resp(429, note="7"), core.Resp(429, note="999"), core.Resp(200, "ok"))
        core.get("https://example.test/b")
        self.assertEqual(self.sleeps, [7.0, core.MAX_WAIT])

    def test_429_gives_up_after_max_tries(self):
        calls = self.script(*[core.Resp(429)] * 5)
        r = core.get("https://example.test/c")
        self.assertEqual((r.status, len(calls)), (429, core.MAX_TRIES))

    def test_403_is_not_retried(self):
        calls = self.script(core.Resp(403), core.Resp(200, "never"))
        self.assertEqual(core.get("https://example.test/d").status, 403)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.sleeps, [])

    def test_cache_hit_within_24h_and_expiry(self):
        calls = self.script(core.Resp(200, "first"), core.Resp(200, "second"))
        a = core.get("https://example.test/e")
        b = core.get("https://example.test/e")
        self.assertEqual((a.text, b.text, b.cached, len(calls)), ("first", "first", True, 1))
        for f in Path(self.tmp.name).glob("*.json"):
            doc = json.loads(f.read_text())
            doc["t"] = time.time() - core.CACHE_TTL - 5
            f.write_text(json.dumps(doc))
        self.assertEqual(core.get("https://example.test/e").text, "second")

    def test_failures_are_not_cached(self):
        calls = self.script(core.Resp(403), core.Resp(200, "ok"))
        core.get("https://example.test/f")
        self.assertEqual(core.get("https://example.test/f").text, "ok")
        self.assertEqual(len(calls), 2)

    def test_per_host_gap_waits_between_requests(self):
        core.HOST_GAP["example.test"] = 5.0
        self.script(core.Resp(200, "1"), core.Resp(200, "2"), core.Resp(200, "3"))
        core.get("https://example.test/1")
        core.get("https://example.test/2")
        core.get("https://other.test/3")
        self.assertEqual(len(self.sleeps), 1)
        self.assertGreater(self.sleeps[0], 4.0)


class TestScoringAndCli(Base):
    def make(self, **kw):
        base = dict(platform="hn", url="https://x/1", title="t", text="some text", score=100, date="2026-10-01T00:00:00Z",
                    author="a", source="s")
        return core.item(**{**base, **kw})

    def test_rank_orders_by_votes_recency_independence(self):
        now = datetime(2026, 10, 12, tzinfo=timezone.utc)
        strong = self.make(score=900, text="strong one", author="a1")
        old = self.make(score=900, date="2018-01-01T00:00:00Z", text="old one", author="a2")
        weak = self.make(score=1, text="weak one", author="a3")
        ranked = core.score_items([weak, old, strong], now)
        self.assertEqual([i["text"] for i in ranked], ["strong one", "old one", "weak one"])

    def test_repeat_author_and_duplicate_text_lose_independence(self):
        now = datetime(2026, 10, 12, tzinfo=timezone.utc)
        a = self.make(text="same words", author="spam")
        b = self.make(text="same words", author="spam")
        c = self.make(text="other words", author="other")
        core.score_items([a, b, c], now)
        self.assertLess(b["rank"], a["rank"])
        self.assertLess(a["rank"], c["rank"])

    def test_unknown_date_and_score_are_neutral_not_crash(self):
        it = self.make(score=None, date="")
        core.score_items([it])
        self.assertTrue(0 < it["rank"] < 1)

    def test_undated_items_rank_below_dated_even_with_votes(self):
        now = datetime(2026, 10, 12, tzinfo=timezone.utc)
        undated = self.make(score=5000, date="", text="snippet")
        dated = self.make(score=0, date="2020-01-01T00:00:00+00:00", text="old post")
        out = core.score_items([undated, dated], now)
        self.assertEqual(out[0], dated)
        self.assertLess(undated["rank"], dated["rank"])

    def test_unique_sources_counts_platform_source_pairs(self):
        items = [self.make(source="a"), self.make(source="a"), self.make(source="b"), self.make(platform="reddit", source="a")]
        self.assertEqual(core.unique_sources(items), 3)

    def test_quote_cuts_on_sentence(self):
        self.assertEqual(core.quote("One sentence here. Second sentence. " + "x" * 400, 40), "One sentence here. Second sentence.")

    def test_normalized_fields_and_author_hash(self):
        self.use(Fake())
        doc = read.run(["hn", "github", "stackoverflow"], "sqlite", limit=3, threads=0)
        need = {"platform", "source", "url", "title", "text", "score", "date", "author", "kind", "scope", "quote", "rank"}
        for i in doc["items"]:
            self.assertTrue(need <= set(i), i.keys())
        names = {"alice", "bob"}
        self.assertFalse(any(i["author"] in names for i in doc["items"]))
        self.assertEqual(core.author_hash("alice"), core.author_hash("alice"))
        self.assertEqual(len(core.author_hash("alice")), 10)
        json.dumps(doc)  # --json must serialize

    def test_cli_parallel_multi_platform_and_unknown_platform(self):
        self.use(Fake(blocked={"https://old.reddit.com": 401}))
        doc = read.run(["reddit", "hn", "x"], "r/programming python", limit=3, threads=0)
        self.assertEqual(doc["stats"]["routes"]["x"], "chrome")
        self.assertIn("hn", doc["stats"]["routes"])
        self.assertTrue(any(g["platform"] == "x" for g in doc["gaps"]))
        with self.assertRaises(SystemExit):
            read.run(["myspace"], "q")

    def test_reader_crash_becomes_gap(self):
        def boom(*a, **k):
            raise ValueError("bad")

        orig = rd.READERS["hn"]
        rd.READERS["hn"] = boom
        try:
            doc = read.run(["hn"], "q")
        finally:
            rd.READERS["hn"] = orig
        self.assertIn("reader error", doc["gaps"][0]["gap"])

    def test_render_text_lists_gaps_and_counts(self):
        self.use(Fake())
        text = read.render(read.run(["hn"], "sqlite", limit=3, threads=0))
        self.assertIn("unique sources", text)
        self.assertIn("news.ycombinator.com/item?id=", text)


@unittest.skipUnless(os.environ.get("SIGMARESEARCH_LIVE") == "1", "set SIGMARESEARCH_LIVE=1 for the live smoke test")
class TestLiveSmoke(unittest.TestCase):
    def test_live_selftest_has_no_fail(self):
        self.assertEqual(read.selftest(list(rd.SELFTEST)), 0)


if __name__ == "__main__":
    unittest.main()
