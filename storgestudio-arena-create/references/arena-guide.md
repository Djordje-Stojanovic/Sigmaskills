# Arena: rank any set of options by the user's blind picks

An **arena** shows the user two options side by side, names hidden, sides random, and asks "which is better?" on one or more metrics. From the user's picks it builds an Elo board (the LMArena method) per metric and overall. It works for anything that can be shown or played: AI models and settings (images, video clips, voices, music), captions, titles, hooks, thumbnails, outfits, logos, intros, script lines.

Built from two real arenas: a video-model arena (400 picks) and an image-model arena (200 picks). The kit is [`../kit/`](../kit/README.md): copy `template/` into the project, fill `arena.json`, run `python server.py`. Skill: **`storgestudio-arena-create`** (it grills the user first).

Use the arena for / keep elsewhere:

| Use the arena for | Keep in |
|---|---|
| 4+ options of the same kind, where taste decides and the user wants a ranking | — |
| 2–3 options for one decision (pick a thumbnail, approve a draft) | Just ask the user |
| Judging one step's quality against a reference | A review pass |
| Facts, measurable checks (length, loudness, frozen frames) | Scripts |

## Requirements

- Python 3 (stdlib only: no pip install), any modern browser. Verified with the self-test and the caption demo (screenshots in `kit/screenshots/`).

## Where it lives

```
<project>/arena/               (any folder inside the project)
  server.py  arena.py  index.html  make_items.py  selftest.py   ← copied from kit/template/
  arena.json                     ← title, question, metrics, groups (prompts, refs), players (labels), anchors, items, settings
  refs/                          ← optional reference media per group (the photos or voice every option must match)
  media/<player>__<group>[__<take>].<ext>  (+ same-name .json sidecar: seconds, GiB, cost ...)
  picks.jsonl                    ← append-only, one line per pick (undo = a line that cancels one)
  codes.json                     ← the blind codes (the page never sees a name or file name)
  results.md / results.json      ← the board, rewritten whenever the Board tab or /api/state is read
```

## The loop

1. **Grill** (the skill does it): what is ranked, the groups, the metrics, how many options and takes, who makes them, how long it may take, what decides at the end.
2. **Make the options**, at most ~20 players; 2–3 takes each where chance plays a role (seeds, voice takes). Put the measured cost in a sidecar per item (seconds, GiB, money).
3. `python make_items.py media/` (or `options.tsv` for text), then set the labels, groups and metrics in `arena.json`.
4. `python selftest.py` (engine, anchors and refs check, ~20 s), `python server.py --open`. Ports: **3410–3499** (the server takes the first free port; keep other servers off this range).
5. Tell the user the link and the keys. The user ranks; the agent watches `results.md` and answers questions with the numbers.
6. **The user says when it is enough.** Then the winners become defaults, the losers are deleted, and the board goes into the ticket or the project notes.

Keys: per metric row `Q W E`, `A S D`, `Y X C` (`Z X C` on QWERTY), `U I O`, `J K L` (A better · same · B better). The page reads the key position (`e.code`), not the letter, so the left hand works on QWERTZ and QWERTY. The arrows do not vote. `↵` next (saves the answered metrics; all answered = saves by itself), `B` both bad, `⌫` undo, `F`/`G` or a click = full size of A/B (`Space` switches, `Esc` closes), `1`/`2` play A/B (audio), `N` note. `#board` in the URL opens the board.

Refs: click a reference thumbnail = full size, `←`/`→` = next reference, `R` = all references in a grid. `F`/`G` show the references in a column beside the option.

## Refs and anchors (config)

- **Refs:** a group can have `"refs": ["refs/a.jpg", {"src": "refs/b.wav", "label": "voice"}]`. The page shows them as thumbnails in the prompt bar. Their size follows the window height. Refs are per group, the same for both sides, so they do not break blindness. An arena without refs works as before.
- **Anchors:** `"anchors": ["gpt", "old-default"]` lists reference players (a cloud model, today's default). They get a rating on the board, but they never take a top-K place: the top-K boost and the "out" cut count non-anchors only. When an anchor has `settings.anchor_games` games (default 8), its pairs get ×0.1 weight, so the picks go to the real candidates.
- **Metric weight:** `{"id": "likeness", "weight": 2}` makes a metric count ×2 in Overall.

## How the ranking works (and why)

| Rule | Why (where we learned it) |
|---|---|
| Bradley-Terry fit (MM algorithm) on Elo points: 1000 = average, +100 = wins 64 % | The LMArena method; pairs that never met still connect through shared opponents |
| A tie or "both bad" = half a win each | The user says "all the same" a lot (video arena); a tie is information, not noise |
| Prior: each player drew once vs an average player | One lucky win must not put a newcomer on top (video arena) |
| Bootstrap 95 % range per rating; overlapping ranges = not settled | "Is #2 really better than #3?" is answered by the range, not the rank (image arena) |
| One rating per player; its takes (seeds, versions) pool | One seed can lie: a setup led on 1 seed only (video arena) |
| Pairs only inside one group (same prompt, same scene) | Comparing a gym photo with a selfie says nothing (both arenas) |
| One board per metric + Overall (weighted mean of the answered metrics) | The Picture winner is not the Prompt winner (image arena); a metric can weigh 2 (prompt following in the video arena) |
| Only the answered metrics count | The user sometimes judges only one thing; "unanswered" must not become "same" |
| Pair picker: closeness × uncertainty ÷ times met; met 3+ = nearly retired; the last 3 players damped; drawn from the top 12, never the same argmax | The user (video arena): "why am I always comparing the same things instead of crossmatching?" |
| Newcomers (< 4 games) ×4, new-vs-new as often as new-vs-leader | Otherwise new prompts and new setups are never shown (video arena) |
| Out: 0 wins after 3 losses, or the best case under the K-th's worst case after 6 games | Stop spending picks on clear losers (both arenas); a grey row means "out" and nothing else |
| Every ~14 picks a judged pair comes back with sides swapped | Consistency: the user's normal is ~65–70 %; below ~55 % the metric or the options are unclear |
| Retire a group (`"retired": true`), never overwrite it | Old picks stay valid when a prompt is swapped (image arena) |
| `skip` per group: `{"P5": ["gpt"]}` | A cloud model that refuses a prompt sits it out without a loss (image arena) |
| Anchors: rated, never a top-K place, ×0.1 picks after `anchor_games` | A strong reference in the top K took the top-K boost and soaked up picks; a real candidate was cut as "out" (image arena, round 3) |

## Lessons for great arenas

1. **Hard groups decide, easy ones don't.** Pick prompts or briefs where the options can fail: many named people, lettering, uncensored content, a specific date or opponent the user can check. Easy prompts left the image board flat (image arena).
2. **Test on the user's own prompts, not only ours.** The video leader on our prompts lost on their 3 ideas (video arena).
3. **Keep today's default in as a baseline,** and a strong outside reference (GPT Image, a pro thumbnail) when one exists: the gap tells whether local is good enough. **Make every reference player an anchor** (`"anchors"`). If not, the top-K boost feeds it picks, and it pushes real candidates out (image arena, round 3).
4. **Write down where each option came from** (Reddit, the official README, the agent's own idea). The only certain loser in the image arena was the agent's untested LoRA stack; say so plainly.
5. **Measure the cost of every option** (seconds, GiB, money) in a sidecar: the board shows it next to the rating, and ties go to the cheaper one. Speed breaks ties unless the user says speed matters more.
6. **Change one thing per option** when you test settings (quant, steps, size), or the board can't tell what helped.
7. **Judge add-ons (upscalers, face fixes, LoRAs) on the hardest group,** with the same base with and without them; the upscale looked useless after 110 picks and won after the hard prompts (image arena).
8. **Group the renders by model file** and render takes before new players; a model switch costs minutes (image arena).
9. **≤ 20 players, 2–3 takes each, 3–6 groups.** About 10–15 picks per player give a usable top 3; the user stops when they want.
10. **The user decides when it is enough, never the agent.** Report: picks, consistency, which places are settled (ranges apart) and which are a tie.
11. **Present the board as a table:** Elo, range, games, W-L-T, the cost columns, per metric. Say "tie" when ranges overlap; don't crown a winner the data doesn't support.
12. **Blind means blind:** no names, file names or sizes on the rank page; random sides; equal display size; the board tab warns that looking breaks blindness.
13. **Never present an idea as the user's** and never edit the user's picks; `picks.jsonl` is append-only.
14. **Don't break a live arena.** Back up every file before editing a running one; restart only your own server PID.
15. **Show the references when likeness counts.** Put the photos in the group's `refs`. The user must see them big: click for full size, `R` for all, and a column beside the zoomed option (image arena, round 3).
16. **Keys go by position, not by letter.** On QWERTZ the bottom-left row is `Y X C`. The arrows no longer vote, because they now move between references (image arena, round 3).

## Rules and gotchas

- Parallel safety: one port per arena from 3410–3499; all state is in the arena folder.
- Outward-facing: none. The server listens on 127.0.0.1 (`--lan` for a phone, only when the user asks).
- Gotchas: write `arena.json` as UTF-8 (`ensure_ascii=False` + `encoding="utf-8"`), or a "·" turns into "Â·"; Chrome needs HTTP Range for video and audio seeking (the server has it).

## Reference

- Kit: [`../kit/README.md`](../kit/README.md) (copy recipe, screenshots). Template: `kit/template/`. Example config: the caption arena in `kit/template/arena.json`.
