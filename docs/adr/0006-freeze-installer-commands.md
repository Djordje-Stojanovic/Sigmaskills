# Freeze installer commands; merge the adopt flags after 0.4.0

The Sigma Installer is about 11,000 lines of code that deliver about 100 KB of Markdown. It has ten commands and twelve resolution flags, and there is no usage data for `purge`, `restore`, or `uninstall --all`. Each new path multiplies the cases that tests and Releases must cover. So the owner decided (issue #44, 2026-09-27):

1. No new installer commands until the open P2 tickets under #31 are closed. `install --all` and several skills in one `install` (#38) extend an existing command and are allowed.
2. The four `--adopt-changed`, `--adopt-legacy`, `--adopt-unverified`, and `--adopt-malformed` flags stay unchanged in 0.4.0. After 0.4.0 they merge into one `--adopt <replace|skip|export>` flag; the old flags stay as hidden aliases for one minor Release. #35 already removes most `unverified` cases, so the merged flag is rarely needed.
3. `purge`, `restore`, and `uninstall --all` stay. They are built and tested, but they get no new features.

## Consequences

0.4.0 ships with no flag migration, so no user script breaks in this Release. New installer features need a written reason that names the user problem. The flag merge is tracked as its own ticket.
