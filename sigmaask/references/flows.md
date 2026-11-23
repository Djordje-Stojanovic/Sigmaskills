# Flows

Use this map as guidance, not as a lookup table. Every edge here comes from the SKILL.md of the skills it names. Check the edge against the skill's own file before you recommend it, because a skill can change after this map was written.

## Worked examples

Each example shows the reasoning, so read for the method more than the answer.

- **Nothing yet** ("I want to build an app for X"). No repo and no plan, so a build skill has nothing to work on. Sharpen the idea first: `/sigmamusk` with no target grills it in one message. With Matt's pack and a repo, `grill-with-docs` does the same and leaves a glossary behind. Then `to-spec`. Add SigmaResearch when the user does not know what already exists.
- **An idea inside a repo** ("vague idea for a feature"). The repo gives context, so `/sigmamusk <the idea>` can question the idea, cut it down and file one issue with a Done-when. SigmaShip then ships that issue. When the idea is too big for one session, use `grill-with-docs` → `to-spec` → `to-tickets`.
- **A plan with open questions.** If many topics are open, SigmaDebug settles them one at a time. If the plan is clear but large, `to-tickets` and then SigmaShip per ticket, or SigmaLoop to run it overnight.
- **A build that half works.** Check whether one thing is broken or many. One bug: `diagnosing-bugs` first. A flaky test is that same loop, because it needs a command that fails on demand. Then SigmaShip with the regression test. Many unknowns: SigmaReview on the repo.
- **Before a release.** SigmaReview proves what would hurt users. SigmaTaste plans the visible polish.
- **A mess** (a repo, a disk or a skill folder that has grown). `/sigmamusk cut` or `/sigmamusk reset`. The scan's duplicate and retired lines are already part of the evidence.
- **Not code** (slides, a video, a stock, a course). Search the registry with the user's words and file types. Recommend the installed skill that fits, or the best one with its install line.

## The two loops

**Fix loop: what is wrong.**
`SigmaReview → SigmaBrief → fix PRs → merge`

- SigmaReview proves defects (bugs, security, slow paths) and publishes one PR that adds `SIGMAREVIEW-YYYY-MM-DD.md`. Each finding is a self-contained fix brief, grouped into waves that can run in parallel.
- SigmaBrief turns a report, a wave or a list of issues into paste-ready briefs for other agents, in safe parallel waves. It writes briefs and does no fixing.
- A finding filed as an issue with a Done-when goes to SigmaShip instead.

**Grow loop: what would make it better.**
`SigmaImprove → category issues → SigmaShip`

- SigmaImprove compares the product with the world's top 1-3 and keeps one living issue per category. Each entry has a `Done when:` line, so SigmaShip can ship it.
- Several entries at once go through SigmaBrief, or through SigmaLoop for an unattended run.

**SigmaShip** is the end of both loops. It ships one issue with acceptance criteria: a test-first PR, a self-review (a second-agent review only on request), then the merge. `sigmaship stop` ends at a ready PR. Without criteria, its own table sends you to `to-spec`/`to-tickets`, to `grilling`, or to SigmaReview/SigmaImprove.

## On-ramps

| Situation | Path | Note |
|---|---|---|
| A vague idea, a plan or a feature | `/sigmamusk <target>` → one issue → SigmaShip | `/sigmamusk` alone grills first (3-5 questions). It questions and deletes before it builds. |
| A big build, many sessions | `grill-with-docs` → `to-spec` → `to-tickets` → SigmaShip (or `implement`) per ticket | Matt Pocock pack. A foggy greenfield effort: `wayfinder` first. |
| One bug | `diagnosing-bugs` → regression test → SigmaShip | SigmaDebug says "not for one bug". |
| Many open topics or doubts | SigmaDebug | Settles one topic at a time. Each fix ships in a background agent through SigmaShip. |
| The same correction a second time | SigmaCorrect → SigmaShip | It turns the correction into a check or a test. A one-time bug is not a repeat. |
| Work to run unattended | SigmaLoop → paste the prompt into the host | SigmaLoop writes the prompt and a loop file. It never starts the run. |
| Cloud machines for that work | SigmaBoat | CPU boxes on boat.dev. A GPU or TPU job goes to SigmaCollab. |
| A bloated repo, machine or setup | `/sigmamusk cut <repo>` or `/sigmamusk reset` | It measures the waste first. The owner decides what stays. |

## What comes after each skill

| After | Next |
|---|---|
| SigmaReview | SigmaBrief on the report, or fix the first wave |
| SigmaImprove | SigmaShip on one entry; SigmaBrief or SigmaLoop for many |
| SigmaMusk | SigmaShip on the issue it filed |
| SigmaTaste | `/sigmaloop` to run the plan, `/sigmaship` for one ticket, or `implement-spec` |
| SigmaCorrect | SigmaShip for the check |
| SigmaResearch | `grill-with-docs` or `to-spec` with the findings; SigmaImprove when it is about a product |
| SigmaLoop | paste the prompt; SigmaBoat for workers |
| SigmaShip | done. When the same review comment comes back twice: SigmaCorrect |

## Standalone Sigma skills

| Job | Skill | Not for |
|---|---|---|
| Read public sources (Reddit, X, HN, GitHub, YouTube, arXiv, SEC) | SigmaResearch | posting or replying |
| Look inside video, audio, scans, odd Excel, sqlite, binaries | SigmaDeepLook | plain text, CSV, JSON, code |
| Plain English, status boards, less jargon | SigmaWrite | rewriting code or APIs |
| Make a draft read human, or write a script | SigmaHuman | cutting jargon (SigmaWrite) |
| A ranked plan of visible changes to a page, app, deck or film | SigmaTaste | building the changes |
| A visual tour of a codebase | SigmaTour | reviewing it |
| Make a score better, one kept-or-reverted change at a time | SigmaClimb | a goal nobody can score |
| Rank many options blind, Elo per metric | SigmaCreateArena | 2-3 options |
| Make or install a new skill | SigmaCreate | a correction given twice |
| A course, tutorial or guide | SigmaCourse | live tutoring |
| Any money question: a stock, a deal, a purchase, a loan | SigmaFinanceMan | questions with no money in them |
| Rent a GPU, TPU or big CPU for one job | SigmaCollab | CPU dev boxes |
| Set up a repo after install, sync house files | SigmaSetup | installing skills |
| Remove model-written refusals from a repo | SigmaFreedom | adding restrictions |

## Other packs

Use these when no Sigma skill fits, or when the user already works in that pack. The scan shows what is installed.

| Pack | Flow or use |
|---|---|
| Matt Pocock | `grill-with-docs` → (`prototype`) → `to-spec` → `to-tickets` → `implement` or `implement-spec` (with `tdd` and `code-review`) → `retro`. On-ramps: `triage` for incoming issues, `diagnosing-bugs`, `wayfinder`. His router is `ask-matt`. |
| Superpowers | `brainstorming` → `writing-plans` → `executing-plans` or `subagent-driven-development` → `test-driven-development` → `requesting-code-review` → `finishing-a-development-branch`. `systematic-debugging` for bugs. |
| Agent Skills (Addy Osmani) | `idea-refine` → `spec-driven-development` → `planning-and-task-breakdown` → `incremental-implementation` → `code-review-and-quality` → `shipping-and-launch` |
| tstack | PR tools: `file-pr`, `babysit-pr`, `takeover`, `modernize`, `leaving-pr-comments`; `council` and `full-send` on their trigger words |
| Ponytail | the smallest change that works; `ponytail-review` and `ponytail-audit` for reports |
| Design | `frontend-design` (Anthropic), `impeccable`, `taste-skill`, `hallmark`, `emil-kowalski`, the design-md pack (pick 3 at a time); SigmaTaste for the critique |
| Documents | Anthropic: `docx`, `pdf`, `pptx`, `xlsx` |
| Video and slides | HyperFrames: `hyperframes`, `slideshow` |
| Research | SigmaResearch; `last30days` for the last month only; Matt's `research` for a cited file in the repo |
| Finance | SigmaFinanceMan; the Financial Services pack for bank-style models and decks |
| Security | `security-audit` (Cloudflare); Claude-Red for offensive security work |
| Marketing | `marketingskills`, `linkedin`, `baoyu` |

## Retired names

The scan prints each retired skill that is still installed, with the skill that replaced it. The map lives in `manifest.json` (`replacedBy`).
