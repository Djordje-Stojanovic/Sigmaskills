# Counting depth

Use this when the user asks for a number of sources, a number of sites, or "deep" research with a plan. Without a number there is no quota.

## Definitions

- **Meta source:** a site or platform family: Reddit, X, YouTube, Bilibili, Weibo, Zhihu, Baidu Baike, Xinhua, Wikipedia, a ministry site. Take it from the URL: a known platform family, else the registered domain. Do not take it from your own label, so a label cannot add meta sources.
- **Source:** one unique page or thread read **in full**: a post with all its comments, an article body, a video's full subtitles or transcript.
- **Digest:** a search result, snippet, headline, AI summary or feed excerpt. It counts 0. Log it as `read=digest` so the next run skips the dead end.
- **Same URL again**, in a later round or by another agent, counts once. A `read=full` line beats a `read=digest` line for the same page.
- **Different pages on one site** count separately, up to `per` per meta source. Pages beyond `per` do not count.

## Plan words

`meta=10 per=10 full=100`: how many meta sources, the most that count per meta source, and the total read in full. This is the default. Optional: `rounds=2 agents=2`, `split=china:50,serbia:20,west:30` (a minimum of full sources per region) and `must=reddit,x,youtube` (each needs one full source). Region comes from the language and site (Chinese, Serbian or other), or from a `region=` cell. Only logged words bind.

## The source log

One numbered line per source, in the order you read them. A markdown table row with the same cells also works. An older log with a Tag column reads F, R and S as full and D as digest.

```text
N. meta source | URL | date | language | read=full|digest | words read | takeaway
12. Xinhua | https://www.news.cn/auto/20261008/1a53/c.html | 2026-10-08 | zh | read=full | 881 | FAW, Toyota and GAC sign a framework: "<original quote>"
```

- `date`: the page date as `YYYY-MM-DD`, or `unknown`.
- `language`: `en`, `zh`, `sr`, `de` and so on. For a page that is not English, the takeaway keeps the original quote.
- `read=full` needs the whole page. A line with no `read=` word counts as a digest.
- A blocked URL is a `read=digest` line with the status in the takeaway.

## Check it

```bash
python scripts/source_log.py research/a-sources.md research/b-sources.md --plan "meta=10 per=10 full=100"
```

It prints the tally by meta source, language and region, lists what is over the cap, and exits 1 while the plan is not met. Read the missing pages in the short meta sources and regions; never relabel a digest as full.

## Rounds

Round 1 fills each meta source with full reads. A gap round then reads exactly what the check says is short. A re-read of a site in round 2 counts as new only when it is a different page.
