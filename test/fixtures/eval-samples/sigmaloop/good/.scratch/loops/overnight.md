# Loop: Snake Lite issues 1 and 2

Host: Claude Code /loop. Stop line: 2026-10-20 07:00 Europe/Vienna. Re-read this file at every wake: edits apply on the next wake.

## Stance
Plan to finish both issues by the stop line. Never idle. Always end a turn with ScheduleWakeup.
Authorised: commit on a feature branch. Nothing else.

## Goal
At the stop line docs/issues/1-wall-collision.md and docs/issues/2-pause.md are ticked with dated evidence, or carry a dated log line.

## Crew
Solo, one item at a time.

## Each wake
1. Read the clock. At or after 07:00: Finish.
2. Re-read the issue files.
3. Work the next item.
4. Update the handoff.
5. ScheduleWakeup.

## Priority
1. Issue 1, wall collision. 2. Issue 2, pause.

## Landing
- Test first, then code. `npm test` green.
- Tick the issue file with the date and the test name.

## Finish
Start nothing new. Write the final handoff. ScheduleWakeup with stop: true.
