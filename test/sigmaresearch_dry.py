"""Offline check of the SigmaResearch parsers for the X, arXiv and SEC routes. No network: fixed answers in the hosts' shapes."""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sigmaresearch", "scripts"))
import sr_readers as rd  # noqa: E402

URL = "https://x.com/jack/status/20"

vx = rd.parse_x_vx({"text": "just setting up my twttr", "likes": 5, "replies": 2, "date_epoch": 1142974214,
                    "user_screen_name": "jack"}, URL)
assert vx[0]["text"] == "just setting up my twttr" and vx[0]["score"] == 5 and vx[0]["date"] == "2006-03-21T20:50:14Z", vx
assert rd.parse_x_vx({}, URL) == []

oe = rd.parse_x_oembed({"author_name": "jack", "html": '<blockquote><p lang="en">just setting up my <b>twttr</b></p>&mdash; jack '
                        '<a href="https://x.com/jack/status/20">March 21, 2006</a></blockquote>'}, URL)
assert oe[0]["text"] == "just setting up my twttr" and oe[0]["date"] == "2006-03-21", oe
assert rd.parse_x_oembed({"html": ""}, URL) == []

ATOM = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/1706.03762v7</id>
<title>Attention Is All
 You Need</title><summary> The dominant models. </summary><published>2017-06-12T17:57:34Z</published>
<link href="https://arxiv.org/pdf/1706.03762v7" rel="related" title="pdf"/><category term="cs.CL"/>
<author><name>A</name></author><author><name>B</name></author></entry>
<entry><id>http://arxiv.org/api/errors#bad</id><title>Error</title></entry></feed>"""
ax = rd.parse_arxiv_atom(ATOM)
assert len(ax) == 1 and ax[0]["url"] == "https://arxiv.org/abs/1706.03762" and ax[0]["title"] == "Attention Is All You Need", ax
assert ax[0]["pdf"].endswith("1706.03762v7") and ax[0]["authors"] == 2 and ax[0]["source"] == "arxiv.org/cs.CL"
for t in ("1706.03762", "https://arxiv.org/abs/1706.03762v7", "https://arxiv.org/pdf/1706.03762.pdf", "arXiv:hep-th/9901001"):
    assert rd.ARXIV_ID.search(t), t
assert not rd.ARXIV_ID.search("attention transformer")

ab = rd.parse_arxiv_abs('<meta name="citation_title" content="Attention Is All You Need" />'
                        '<meta name="citation_date" content="2017/06/12" /><meta name="citation_abstract" content="Short." />',
                        "https://arxiv.org/abs/1706.03762")
assert ab[0]["title"] == "Attention Is All You Need" and ab[0]["date"] == "2017-06-12", ab

hits = {"hits": {"hits": [{"_id": "0000320193-26-000026:aapl-20260926.htm", "_source": {
    "ciks": ["0000320193"], "display_names": ["Apple Inc.  (AAPL)  (CIK 0000320193)"], "form": "10-K",
    "file_date": "2026-10-31", "file_type": "10-K", "period_ending": "2026-09-26"}}]}}
fs = rd.parse_sec_search(hits)
assert fs[0]["url"] == "https://www.sec.gov/Archives/edgar/data/320193/000032019326000026/aapl-20260926.htm", fs
assert fs[0]["source"] == "sec.gov/Apple Inc." and fs[0]["date"] == "2026-10-31"

facts = {"entityName": "Apple Inc.", "facts": {"us-gaap": {"Assets": {"units": {"USD": [
    {"val": 1, "end": "2025-09-27", "filed": "2025-10-31", "form": "10-K"},
    {"val": 2, "end": "2026-09-26", "filed": "2026-10-31", "form": "10-K"},
    {"val": 9, "end": "2027-01-01", "filed": "2027-01-02", "form": "8-K"}]}}}}}
ff = rd.parse_sec_facts(facts, "320193")
assert len(ff) == 1 and ff[0]["value"] == 2 and ff[0]["unit"] == "USD", ff

assert "admin@example.com" in rd._sec_headers()["User-Agent"]
os.environ["SEC_USER_AGENT"] = "Someone someone@example.org"
assert rd._sec_headers()["User-Agent"] == "Someone someone@example.org"
print("sigmaresearch dry: ok")
