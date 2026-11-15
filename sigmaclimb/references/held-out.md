# The held-out check

The agent sees every input the scorer uses. After many passes on the same inputs, it can tune to them. A held-out
check runs the same quality check and the same score on inputs the loop never tuned to. It is a tool for the owner,
not a lock: off by default, and never silent.

## First: the owner's own machine

When the owner runs the target on his own machine, his run there is the held-out check. Say that first, in the
interview. He measures the champion in his real use; his word promotes it or sends it back
(`verdict.py promote runs/<n> --owner "<his words>"`). No second input set is needed.

## The three modes (`project.json` "heldout")

| Mode | What it does | When |
|---|---|---|
| `off` | nothing | the default |
| `advisory` | `promote` prints the answer and promotes anyway | the owner wants to see transfer, not block on it |
| `required` | `promote` refuses without a `PASS` for this exact change | only when the owner opts in, in his own words, in the interview |

The owner's word (`--owner`) promotes in every mode, and `champion.json` keeps his words.

## How it works

- `heldout.dir` in `project.json` names a folder. The owner (or the agent, with his inputs) puts `check.py` there:
  it gets the project folder and a run folder, runs that change on the held-out inputs **on the same machine as
  the candidates**, and prints as its last line `{"quality_ok": true, "gain": 0.04}`. The gain is in the visible
  score's unit: ratio - 1, or share of pairs won - 0.5. Everything else it prints is thrown away.
- `heldout.py selftest <project>` runs the check on the unchanged champion first. It must pass the quality stage.
  If it does not, the check is broken: say so to the owner, and do not use it until it passes.
- `heldout.py check <project> runs/<n>` answers one of three, with no numbers:
  - `PASS`: quality held and the gain there is at least `share` (default 0.5) of the visible gain;
  - `FAIL quality`: the quality check failed on the held-out inputs;
  - `FAIL gain`: quality held, but the gain did not transfer.
- The answer is stored per run with the change's hash. A later edit of the change makes it stale.

## When a FAIL comes

- `FAIL quality` on a change that cannot alter the output (order of work, caching, scheduling): the check is
  suspect. Run the self-test again before you believe it.
- `FAIL gain`: the gain may be tuned to the visible inputs. Record it in `ruled_out.tsv` with what it rules out.
- Either way the loop goes on with the next idea, compared with the current champion. A FAIL never stops the loop.

## Keep it honest

- The agent does not read the held-out inputs it did not write, and never puts them into a log.
- If the agent saw an input (a log, an error message), the set is spent: make a new one and say so in `insights.md`.
- An unforgeable answer needs a folder the loop cannot write: another user, or the owner's machine. For a `required`
  check, put `heldout.dir` there.
