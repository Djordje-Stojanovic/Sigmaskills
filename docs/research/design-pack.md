# The design pack: research of 2026-11-10

The question: which skills make a coding agent ship good UI on the first try. The owner asked for a small, high-quality pack, under 20 skills and ideally 10, and asked to track it.

## Verdict

Five skills work, and the owner already had most of them. So the pack is two installs, not a shelf of twenty: add `impeccable` and `taste-skill`, keep `frontend-design` and `sigmataste`. Past about six design skills the pack is one more thing to keep current. One thread reports six months of three stacked design skills that still made the same generic page ([r/ClaudeAI](https://www.reddit.com/r/ClaudeAI/comments/1t24gan/few_months_of_frontenddesign_uiuxpromaxskill/)). The reasonable order of jobs is: direction, system, build, look, fix. Each skill gets one job.

The owner asked for about 10. Five is the research's answer; the owner has not yet said yes to the smaller number.

## The install

```bash
npx @djordje-stojanovic/sigmaskills install --preset design-pack --agent claude --project <repo> --yes
```

`design-pack` installs `impeccable` and `taste-skill`, both at the pinned commits in `registry/packs.json`. Update runs the same way as for any pack, and `skills-lock.json` hashes every installed skill, so a change shows as a diff of hashes. That file is not committed, so the pins are written here and in the registry.

## The five rows

| # | Skill | Source | Job | How it comes |
|---|---|---|---|---|
| 1 | `impeccable` 4.8.2 | `pbakaus/impeccable` | 24 commands (`critique`, `audit`, `polish`, `typeset`). A 62-rule slop detector runs as an edit hook, a CLI, a URL scan or a Chrome overlay. It is the only candidate that reviews a page nobody is watching. Top answer in three Reddit threads. | `design-pack` |
| 2 | `taste-skill` 2.5.1 | `Leonxlnx/taste-skill` | Picks a palette, font pair and hero layout, builds from a starter kit, then proves the page in headless Chrome at four widths. Evidence is thinner: one praise thread, one doubtful thread. | `design-pack` |
| 3 | `frontend-design` | `anthropics/skills` | About 1,500 words of direction. No scripts, no hook, so it cannot break a repo. Best on small work. | `anthropic` pack, one skill: `install frontend-design`. Do not pull all 19. |
| 4 | `sigmataste` | this repo | Looks through 14 lenses, asks one round, writes a ranked plan and stops. Covers decks, docs, film and images, not only web pages. | bundled, part of `core` |
| 5 | `sigmadesign` | this repo | Wrote one `DESIGN.md` per repo, with tokens. | Retired in 0.24.0. Not in the pack. |

Where they overlap: `taste-skill` for a whole landing page, `frontend-design` for small work, `impeccable critique` for a live web page, `sigmataste` for anything that is not a web page or when you want a plan before code.

## Not added

`ui-ux-pro-max` (13 skill files, needs image-generation keys, repeats `sigmadesign`), `superdesign-skill` (every draft needs a login and credits), `hallmark` (same shape as `taste-skill`; a swap, not an addition; it stays a pack of its own), the 84-file `design-md` pack (84 borrowed looks fight the one look of the owner's sites; it caps at 3), `oil-ui` (good method, but in Chinese and needs a vision model and a subagent).

## What the evidence is weak on

- Single-author before and after posts are weak. One author re-ran the test and wrote that the generic cluster "didn't show up once, in either arm".
- `impeccable` is strongest on one component, not "redo the site": one commenter got a broken page from it.
- Star counts are not evidence. A skeptic questioned the stars of `taste-skill`.
- No X replies were read, and r/UXDesign was not reachable.

## Source counts

15 Reddit threads read in full, 5 X posts read in full, 11 GitHub repos (3 read end to end: `taste-skill`, `impeccable`, `oil-ui`; the rest in part). 31 sources, 25 counted as read in full. The ask was 10 Reddit threads, 5 X posts and 5 repos.

## Sources

Reddit (all read in full, via the Arctic Shift archive; Reddit's own JSON was behind a login wall):

- r/ClaudeAI: [1ws9oix](https://www.reddit.com/r/ClaudeAI/comments/1ws9oix/how_are_people_actually_getting_claude_to_build/), [1t24gan](https://www.reddit.com/r/ClaudeAI/comments/1t24gan/few_months_of_frontenddesign_uiuxpromaxskill/), [1rafmpg](https://www.reddit.com/r/ClaudeAI/comments/1rafmpg/im_rating_every_claude_code_skill_i_can_find/), [1ujmgzu](https://www.reddit.com/r/ClaudeAI/comments/1ujmgzu/how_do_i_get_claude_code_to_actually_start_from/)
- r/ClaudeCode: [1t1ocpy](https://www.reddit.com/r/ClaudeCode/comments/1t1ocpy/every_vibe_coded_app_has_the_same_fontenddesign/), [1s2cgdo](https://www.reddit.com/r/ClaudeCode/comments/1s2cgdo/what_do_you_guys_use_in_promptsskills_to_get_less/)
- r/ClaudeDesign: [1v8hli6](https://www.reddit.com/r/ClaudeDesign/comments/1v8hli6/i_ran_the_same_ui_brief_6_times_with_and_without/)
- r/WebAfterAI: [1wekm8s](https://www.reddit.com/r/WebAfterAI/comments/1wekm8s/6_skills_that_make_aibuilt_frontends_look_less/)
- r/webdev: [1sbeupa](https://www.reddit.com/r/webdev/comments/1sbeupa/using_ai_to_generate_your_designs_and_shipping/), [1opi62a](https://www.reddit.com/r/webdev/comments/1opi62a/with_ai_are_we_all_just_shipping_the_same_ui_over/)
- r/UI_Design: [1tvb91q](https://www.reddit.com/r/UI_Design/comments/1tvb91q/ai_fatigue_from_same_designs/), [1tnqbcw](https://www.reddit.com/r/UI_Design/comments/1tnqbcw/issue_with_ai_agent_taste_skills/)
- r/agency: [1skbxo0](https://www.reddit.com/r/agency/comments/1skbxo0/an_entitled_rant_about_homogenous_aigenerated/); r/website: [1qrov8o](https://www.reddit.com/r/website/comments/1qrov8o/how_make_aibuilt_websites_look_unique/); r/codex: [1ss2dnd](https://www.reddit.com/r/codex/comments/1ss2dnd/frontend_solved_with_images_taste_skill/)

X (posts only, replies not read): [pbakaus 2041999176683418064](https://x.com/pbakaus/status/2041999176683418064), [pbakaus 2079984598105358828](https://x.com/pbakaus/status/2079984598105358828), [pbakaus 2100284971961430019](https://x.com/pbakaus/status/2100284971961430019), [LexnLin 2118860490734707053](https://x.com/LexnLin/status/2118860490734707053), [chetaslua 2109377452665618760](https://x.com/chetaslua/status/2109377452665618760)

GitHub: [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill), [pbakaus/impeccable](https://github.com/pbakaus/impeccable), [oil-oil/oil-ui](https://github.com/oil-oil/oil-ui), [t3dotgg/tstack](https://github.com/t3dotgg/tstack), [anthropics/skills](https://github.com/anthropics/skills), [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill), [superdesigndev/superdesign-skill](https://github.com/superdesigndev/superdesign-skill), [Nutlope/hallmark](https://github.com/Nutlope/hallmark), [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines), [t3dotgg/ui-design-bench](https://github.com/t3dotgg/ui-design-bench), [t3-oss/create-t3-app](https://github.com/t3-oss/create-t3-app)
