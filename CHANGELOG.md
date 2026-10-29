# Changelog

All notable changes to [Sigmaskills](https://github.com/Djordje-Stojanovic/Sigmaskills) are documented here.

## Ticket 83 (2026-10-19 to 2026-10-25)

79 merged pull requests and 81 commits on `main`, shipped as the releases below (each has its own section in this file); the last is 0.16.12 on 10-25, after four more sigmadeeplook fix rounds (#187 to #198). The picture across all four repos: the [ticket 83 changelog page](https://claude.ai/artifact/U1Z7U3z1BMFVu3rUPXAdMJ).

| Release PR | Merged (Vienna) | Title |
|---|---|---|
| [#119](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/119) | 10-19 03:53 | release: 0.10.0 - sigmaloop, sigmataste, sigmaship upgrade |
| [#131](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/131) | 10-20 03:57 | release: 0.11.0 - sigmahuman, sigmaresearch persistence ladder, sigmaloop host files |
| [#136](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/136) | 10-20 15:03 | Release identities for 0.12.0 |
| [#139](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/139) | 10-20 17:36 | release: identities for 0.13.0 (sigmafork course v2) |
| [#142](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/142) | 10-21 01:31 | release: identities for 0.14.0 (sigmatour, sigmaresearch Reddit/X routes) |
| [#147](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/147) | 10-21 09:17 | release: identities for 0.15.0 (sigmafinanceman) |
| [#150](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/150) | 10-21 16:50 | release: identities for 0.15.1 (sigmadeeplook --ask fix) |
| [#152](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/152) | 10-21 18:09 | release: identities for 0.15.2 (Claude Code run mode) |
| [#159](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/159) | 10-22 23:18 | release: identities for 0.16.0 (sigmadeeplook round 8 and cleanup) |
| [#162](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/162) | 10-23 00:48 | release: identities for 0.16.1 (sigmadeeplook fix round 9) |
| [#165](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/165) | 10-23 01:47 | release: identities for 0.16.2 (skill descriptions at 200 characters) |
| [#167](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/167) | 10-23 11:52 | release: identities for 0.16.3 (sigmafinanceman masters and method) |
| [#172](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/172) | 10-23 13:06 | release: identities for 0.16.4 (sigmadeeplook S13 round 2, sigmafinanceman FRED fallback) |
| [#175](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/175) | 10-23 14:39 | release: identities for 0.16.5 (sigmadeeplook fix round 10) |
| [#179](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/179) | 10-23 17:32 | release: identities for 0.16.6 (sigmadeeplook fix round 11) |
| [#182](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/182) | 10-23 19:54 | release: identities for 0.16.7 (installer pack fix) |
| [#185](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/185) | 10-23 21:07 | release: identities for 0.16.8 (four new packs) |
| [#189](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/189) | 10-24 02:25 | release: identities for 0.16.9 (sigmadeeplook fix round 12) |
| [#192](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/192) | 10-24 19:54 | release: identities for 0.16.10 (sigmadeeplook fix round 13) |
| [#195](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/195) | 10-24 23:53 | release: identities for 0.16.11 (sigmadeeplook fix round 14) |
| [#198](https://github.com/Djordje-Stojanovic/Sigmaskills/pull/198) | 10-25 02:10 | release: identities for 0.16.12 (sigmadeeplook fix round 15) |

## [Unreleased]

### Changed

- The PR body check no longer asks a pull request whose code files are all tests to name `/code-review`. A test-only change skips the review requirement.
- Agent work runs faster in every skill that briefs, spawns or loops agents, on Claude Code and Codex alike. Small steps, repeated checks, shell waits and idle slots cost more agent time than the model's own thinking; each new rule replaces the slower line.
  - `sigmaloop`: the loop file sets big steps (one job in 10-20 tool calls, inputs by path, one Write per output), checks once at the end, no sleep or poll loops, commits per finished file, and a model per difficulty with each review one model up and at most 2 review rounds. Jobs are given out dynamically: a free slot takes the most valuable eligible item for its model in the same turn, never a fixed lane. A fix round goes to the same agent by a follow-up message (Claude Code `SendMessage`, Codex `send_input`). A repeated headless agent keeps one session (`claude -p --resume`, `codex exec resume`), and every headless call gets closed stdin (`claude -p` otherwise waits 3 s). The Claude Code wake is a 30-60 minute fallback, since agent notifications wake the loop; the 60-120 s check-in wake is gone. The crew question recommends 4 agents by difficulty instead of solo plus one reviewer.
  - `sigmabrief`: `approval: auto` is the default, so the executing agent no longer waits for plan approval (`approval: plan` on request). The next free agent takes the most valuable ready brief. Briefs drop the baseline run, work in big steps, commit as they go and validate once at the end. The worktree cleanup sits once at the end of a brief instead of in three places.
  - `sigmaship`: no baseline run and no per-slice type check; the full checks run once before review, and CI once at land. The reviewer runs one model up, at most 2 rounds, round 2 by a follow-up message to the same reviewer; a review fix runs the full suite once after the last fix. Land drops the second full-diff read.
  - `sigmarefactor`: the full checks run once after the last cut, not after each change. `sigmaspeedloop`: background waiters replace the last two polling lines. `scripts/eval-skills.js` starts `claude -p` with closed stdin.

## [0.17.0] — 2026-10-29

### Changed

- Every skill description now starts with the words that trigger it ("Use when asked for sigmaship, ship #123 or ship this ready ticket"), and the summary follows. An agent reads only the description when it decides to load a skill.
- sigmaship: `sigmaship stop` (or `no merge`) does the same work and stops at a green, reviewed PR for the owner to merge. The merge step now states the owner's standing permission to merge, so models that hesitate to merge go ahead.
- `sigmaship`: the review round starts a sub-agent reviewer by default, on the harness's default sub-agent model, without asking first, so it works the same in Claude Code, Codex, Cursor, Muse Code, T3 Code and pi. A reviewer the user names ("SigmaShip reviewer: GPT-6.1 Sol") runs every round; when the harness cannot run that model, the round goes through T3 Code (`t3 thread start --provider --model`), else the default reviewer with a one-line note.
- README: one short paragraph per skill in the same shape, every skill in the hero list (`writegui` and `arena` were unmarked, `speedloop` was missing), shorter table rows, four install-without-the-wizard examples instead of eight, and the retired SigmaPerformance note removed. The prose cap in `test/repo-invariants.test.js` rises from 1,500 to 2,000 words (owner, 2026-10-29).

### Added

- `sigmaspeedloop` (SigmaSpeedLoop): makes any model serve faster on a rented GPU with no quality loss. It grills the owner on what faster and no loss mean, scaffolds one project from `assets/project-template/` (scripts, TSVs, `project.json`), brings up one box with verified weights, locks a script evaluator (invariants, fidelity gate, speed probes with fixed-length replay turns, A/A bands, verdict), then runs one change per pass with a confirmation run for every keep, until the owner destroys the box. Host-neutral; built from the la125 project (Qwen3.8-Flash-Next on a Vast.ai DGX Spark: prefill +32 %, warm agent turns 58 % faster). `references/lessons.md` lists every mistake and its fix.

## [0.16.12] — 2026-10-25

### Fixed

- `sigmadeeplook` fix round 15, lane F2 (two causes of held-out set 14):
  - Labels and formats: a SAS file (sas7bdat or XPORT) now prints its dataset label and, for each variable, the label, the format (name, width, decimals) and the informat. The file's own bytes are read, so no extra package is needed. `--ask "dataset label"`, `"label of variable X"`, `"format of variable X"`, `"which variables have a date format"` and `"value labels of X"` answer exactly. SPSS and Stata files get the same format and value-label answers.
  - A clause the engine cannot apply is no longer dropped silently. When a question holds "values declared missing do not count", "whole word, any capitalisation", "greater than 22,50", "between 3 and 7", "after 2024-05-01" or "excluding Berlin" and no filter shows it, the number is still given and a `Not applied:` line follows it.
- `sigmadeeplook` fix round 15, lane F1 (three causes of held-out set 14):
  - Values a file declares missing are not values. In an SPSS `.sav`, the user-defined missing codes (single codes, ranges, a range plus a code, string codes) and the system-missing cases drop out of every comparison, count, sum, mean, minimum, maximum and group count. The answer says how many cases it left out and which codes (`User-defined missing values excluded: 41,196 cases (commute_min: codes 999)`). Step 1 has a `Declared missing values` line with each variable's codes and case counts. A question that asks for the raw values ("including the missing codes", "the raw values") keeps them and says so. A Stata or SAS missing value (`.a-.z`, `.A-.Z`) reaches `--ask` as a missing value, not as text, so a column with many of them still counts, sums and averages.
  - "Any capitalisation", "any case", "regardless of case", "irrespective of capitalisation", "whatever the case" and similar make a whole-word match ignore case, for cues, text columns and documents alike. A quoted word inside a bracketed aside ("forms such as 'latarni' do not count") is an example, never a filter. A count made as written now says how many more match ignoring case (`119 cues contain it as written; 187 ignoring case`).
  - A report whose columns sit between pipes under a `-----+-----` rule, with a title line, a header and a subtotal line in every section, is one table: the subtotals and section titles stay out of the rows and are printed as they stand. A number written with a comma in a question is read as a decimal when it has one, two or four digits after the comma, and as the table writes decimals when it has three ("2,250" in a decimal-comma table is 2.25); the answer states the reading. A decimal comma comes back as the file writes it (`4127,385`).

## [0.16.11] — 2026-10-24

### Fixed

- `sigmadeeplook` fix round 14, lane F2 (four causes of held-out set 13):
  - SAS code page: the print of a `.sas7bdat` gives the encoding name and the Windows code page, not only the number (`text encoding windows-1254 (code page 1254, Turkish), SAS code 64`). `--ask "which code page"` or `"which encoding"` answers it. Codes that have no Windows page (latin1, utf-8) say so.
  - Colour counts on palette pictures: `--ask "how many pixels have exactly the colour RGB (30, 170, 180)"` counts every pixel of the picture. It was read as pixel x=30, y=170 before. It also takes `#1eaab4` and `palette index 8`, answers with the count and the share of all pixels, and `--ask "colour table"` lists up to 256 colours with exact counts. Step 1 of a picture with up to 256 colours has an `Ask a colour count:` line. A PCX with 2 to 8 colour planes (the 16-colour EGA layout) is decoded without Pillow.
  - GeoPackage: step 1 has a `Feature layers` line with the geometry type, the srs id, the authority code and name, and the extent of each layer. `--ask "which EPSG code do the feature layers use"` answers it. The `Ask a count:` line of a table with a unique key and a number column now shows `which <key> has the largest <number>` (or smallest), and `--ask` answers that form with the key value. Before, a key written with an underscore (`parcel_no`) did not name its column.
  - Cabinets and zips: the print quotes small text members up to 4 KB, and a checksum list gets room for its hash lines. `--ask "line of <member> for <word>"`, `"what does <member> say about <word>"` and hash or checksum questions show the matching lines of the right member. A cabinet is read without 7-Zip when its folders are stored or MSZIP; an LZX or Quantum folder is named as not decoded, never guessed.
  - Stale prints: a stored look is now tied to the scripts that wrote it. After an upgrade the same file gets the new print and the new answers. Before, a stored look from older scripts was served again (the SAS print still said `encoding code 64`).
- `sigmadeeplook` fix round 14, lane F1 (from held-out set 13):
  - A paged report in fixed-width columns is a table. A rule line of dashes marks the columns, also when it repeats on every page. Title blocks, repeated headers, page markers, form feeds and the totals block stay out of the rows; the totals are printed whole. Comma decimals are numbers. Step 1 gets `Find one record:` and `Ask a count:` with the real column names, and `--ask` counts over a threshold and finds a record by its code. Eight aligned lines without a rule line are read too, but only when they make up most of the text.
  - A word that only names the rows ("messages", "cases", "rows") is never a value filter. "How many messages have a context (msgctxt)?" counts the messages whose context is not empty. This works for any column of any table ("have a plural", "have an assignee").
  - "Longer than N bytes", "shorter than N characters" and "at least N characters" count rows by the length of a text column. The question names the column; otherwise the longest text column is used, and the answer says which. A `.mo` counts the original as the file stores it (context, `0x04`, msgid, `0x00`, plural).
  - A scope word is honoured. "Speaker notes" counts notes only, "slide text" counts slide text only, "title" counts titles only. A file that cannot give the scope is refused, not answered over all text. OpenDocument presentations (`.odp`) now have per-slide text and notes like PowerPoint files.
  - Step 1 of a presentation names the last and first slide. `--ask "title of the last slide"` and `"title of slide N"` answer exactly.
  - `--ask "how many entries of <char variable> are the letter 'S'"` counts the letter over a netCDF char variable and says the unit ("counted per character over 2,400 x 48 = 115,200 characters"). A longer value counts entries. Step 1 shows the form.

## [0.16.10] — 2026-10-24

### Fixed

- `sigmadeeplook --ask` (fix round 13, lane F1, from held-out set 12):
  - A bare number that lies in the range of a unique key column is a lookup on that column: `cost_eur of 7512345` now answers like `cost_eur of the patient with pt_id 7512345`. The look keeps its key columns in `look.json` (`facts.find_keys`). `X of N` no longer reads as "X equals N" when X is a measure. A column called `total` or `value` is a measure in `total of 8031`.
  - The `Find one record:` example is built from the file's own columns, for example `ask "age of pt_id 7000001"`. It runs as printed.
  - "In how many paragraphs does the word 'X' appear? (Each table cell counts as its own paragraph.)" is a text count. Words inside brackets no longer send it to the table route. Table cells of an OpenDocument or PDF text count as one paragraph each, as in a Word file.
  - "In how many cues does the word 'X' appear?" counts subtitle cues. The `.mo` file no longer shows the `flags = 'fuzzy'` form (it keeps no flags), and the netCDF line shows a full "last index" question.
- `sigmadeeplook` fix round 13, lane F2 (facts that held-out set 12 showed only in the 10k print; the first print now carries them or points to the `--ask` that answers them):
  - Link and anchor definitions: step 1 of a reST, Markdown, AsciiDoc, org or LaTeX file gives the count and the first and last one with line numbers (`Explicit targets (.. _label:): 19; first 'a' (line 1), last 'b' (line 1099).`). `--ask "the last explicit target"` (or first, or how many; also link definition, anchor, label) answers it. An anonymous reST target (`.. __:`) is no longer counted as a target.
  - Tree depth: step 1 of an XML file gives the elements per level (root = level 0) and, for an element that nests in itself (OPML `<outline>`), its levels with the outermost as level 1. The JSON, YAML and TOML count line says `max nesting depth (top level = 1)`. `--ask "deepest nesting level"` answers it for all four.
  - New step 1 line `Ask a word count:` for Word, OpenDocument, RTF, PowerPoint, PDF, plain text, Markdown and reST files: the `--ask` form with the right unit (slides, pages, paragraphs) and the rule (whole word, capitals as written). A subtitle file already says it in its `Find one record` line (`how many cues contain the word 'X'`).
  - GeoPackage: step 1 lists `gpkg_contents` (table, data type) with a count per data type, so the feature layers and attribute tables are known at once; a long table gets the counts only. A SQLite file of up to 60 tables lists every table with its exact row count in the first two prints.

## [0.16.9] — 2026-10-24

### Fixed

- `sigmadeeplook --ask` (fix round 12, lane F1, from held-out set 11):
  - A big `.sav` is searched to the last case. A rounding number ("to 1 decimal", "top 5") no longer counts as a key, and a search that fills its keep list says PARTIAL instead of "0 matching".
  - A number in quotes (`time index "3287"`, `pixel "336,519"`, curly quotes, backticks) reads as the plain number in netCDF and picture questions. `(x,y)` alone names a pixel on a picture.
  - Step 1 of every table-like file has an `Ask a count:` line: the count forms `--ask` answers, with the file's own column names.
  - `contain the word 'X'` is a real filter over cue text and text columns: whole word, case as written, `ignoring case` to ignore it.
  - A count whose condition matches no filter now says `no filter matched` and lists what it can do. It no longer answers with the row total (the sbv "1,240 cues" answer). An id or code column is never summed for "how many".
  - A question that writes a table's own name (`gpkg_contents`) is answered from that table, not from a look-alike (`gpkg_ogr_contents`).
- `sigmadeeplook` fix round 12, lane F2 (set 11 wrong answers and print gaps):
  - A frequent-word count now counts what `--ask` counts. The capitalised-word list counted a word joined to a digit or an underscore (`Table11`, `AB1234Capsules`) as the word, so it said 20 where the whole-word count is 19. The line now says it is a case-sensitive count of whole words.
  - `--ask` no longer reads a quoted word as a table question just because the word is `Table`. A question on a paragraph count gives two figures when the letters also sit inside a longer word: `21 paragraphs contain 'Capsules'; 22 paragraphs hold the letters 'Capsules' (1 only inside a longer word, e.g. 'AB1234Capsules')`. An occurrence count adds the same clause. Plain `.txt`, `.md` and `.rst` files are counted too, with their own line numbers (a paragraph is a block between blank lines).
  - Video: a new `Clock:` line gives the container start, every stream start and the first video frame. Black and frozen spans are told from the first video frame, with the container time beside them (`black from 0.0 s to 4.8 s after the first video frame (container time 1.44 s to 6.24 s)`), and the first non-black frame is named. Before, a span "at 0:00" counted from the container start, which is 1.4 s in front of the first frame of a transport stream.
  - New `Heading styles` line for reST and Markdown: headings per underline character (`'-' underline x17`), over-and-under titles, and `#` marks. `--ask "how many headings are underlined with hyphens"` and `"... start with '##'"` answer it.
  - A value that names the file is no longer cut: a path with one value in an XML file (the head title of an OPML file), the last record's fields, document properties, container tags and the first and last row of a table print whole up to 200 characters. A longer value says `(cut, N chars)` and the print says how to get the rest.
  - BMP, PCX and TGA headers state the stored bytes per row with padding, and `--ask "how many bytes does one stored pixel row occupy"` answers it (BMP rows are padded to a multiple of 4 bytes). TGA now has a header line.

## [0.16.8] — 2026-10-23

### Changed

- Four new packs, each pinned to one commit or tag: `anthropic` (19 skills from anthropics/skills), `design-md` (84 brand looks from VoltAgent/awesome-design-md, one skill per brand), `last30days` (mvanhorn/last30days-skill v3.30.0) and `financial-services` (anthropics/financial-services: 62 skills, 10 agents and 27 commands as 99 skills; the MCP connectors an agent needs are named in the skill, not installed). Pick a whole pack or single skills; one owner per skill name still holds.
- Design.md installs at most 3 skills at a time. A 4th pick stops with a choice: `--drop <id>` (repeatable), or in the wizard a list where Enter drops one and Esc keeps all. `--preset design-md` is refused and `--preset all` skips it.
- Pack sources are fetched in parallel (up to four at once), sparse and shallow, and a pinned source is cached in `~/.sigmaskills/cache/git`. A pack source can set `transform` and a pack can set `limit`.
- Wizard: key `0` picks the tenth pack; a limited pack shows `held/3`; installed skills are marked; the filter matches a skill's group.
- `list --packs` stops long lists after eight rows and notes a pack's limit. `list --packs --json` adds `limit` and `group`.
- `scripts/packs-snapshot.js` keeps the packs it does not list.

## [0.16.7] — 2026-10-23

### Fixed

- Installer: a fresh install no longer reports skills as failed or kept.
  - The HyperFrames pack followed a moving head, so 14 skills that upstream folded into `hyperframes` (`embedded-captions`, `faceless-explainer`, `general-video`, `hyperframes-animation`, `-audio`, `-core`, `-creative`, `-keyframes`, `-studio`, `motion-graphics`, `music-to-video`, `pr-to-video`, `product-launch-video`, `talking-head-recut`) failed with "not found in heygen-com/hyperframes". The pack now lists the 7 skills that exist in release `v0.8.188` (`figma`, `hyperframes`, `hyperframes-cli`, `hyperframes-registry`, `media-use`, `remotion-to-hyperframes`, `slideshow`) and clones that tag. A pack source may name a `ref`.
  - One owner per skill name. The Local pack listed Sigma skills again, so the picker wrote them twice and the second copy showed "kept (folder in the way)". The first pack that lists a name keeps it (Sigma first), so each name is listed, counted and written once.
- `sigmadeeplook`: three stray scratch files (`scripts/o9.bin`, `o12.bin`, `o12b.bin`, left in by fix round 11 lane F3 and published in 0.16.6) are removed.

## [0.16.6] — 2026-10-23

### Fixed

- `sigmadeeplook` fix round 11, lane F1 (single-record lookups):
  - New `Find one record:` line in step 1. It names the table, the row count, the unique key column with its first and last key, and the route (`--ask` or `--sql`). It prints only when a unique key exists. Covered: delimited text, `.po`/`.mo`, `.properties`, `.sbv`/`.srt`/`.vtt`, SAS, SPSS, Stata, netCDF (the dimension names), sqlite/gpkg, xlsx/xlsb/ods, jsonl and Parquet.
  - `--ask` returns one record by its key: `Answer: <column> = <value> (where <key column> = <key>; <unit> <position>)`, then the record in full. Keys match across case, accents, Cyrillic or Latin letters and hyphens. A bare number matches exactly. A number after a column name (`visit_id 5650000`, `cue number 840`) is a filter.
  - `--ask` now reads `.sav` (not ZLIB-compressed), SAS and Stata files, `.po`/`.mo` messages, subtitle cues and `.properties` keys as tables. A table over 1,000,000 cells that is asked a pure lookup is read in one pass and only the rows that hold a value of the question are kept (`SIGMADEEPLOOK_ASK_STREAM_CAP`).
  - `--ask` reads one netCDF cell by index or coordinate value (`last time index and station index 17`, 2 decimals), unpacks `scale_factor`/`add_offset` and names fill values.
  - A comparison (`Petal_Length greater than 5.0`) now uses the column whose whole name stands before it. A table inside a text keeps original file line numbers.
- `sigmadeeplook` fix round 11, lane F3 (set 10 miss causes: structure and counts):
  - The identity line shows the file's first 8 bytes in hex, in file order (`magic 950412de 00000000`), for every kind found by its magic bytes.
  - Key/value, YAML and TOML files print a `Comment lines` fact: how many comment lines, at which line numbers, and the first comment block as written. A file version stated in a comment is now in step 1.
  - `--ask "how many times does the word 'X' appear"` and `"in how many paragraphs ..."` count whole words over the full text of a Word, OpenDocument, PDF, PowerPoint or RTF file, case-sensitive when the quoted word has a capital, and name the text they counted. Before, the agent counted over a clipped print and was off by 1 to 4. A document look also lists its ten most frequent capitalised words.
  - Office packages (`.docx`, `.xlsx`, `.pptx`, `.odt`, `.ods`, `.odp`) print their hyperlinks with targets, the pictures and media files with path and size, and footnote, endnote and comment counts.
  - Container headers are read from the file's own bytes, with or without 7-Zip: a cabinet's folders (compression groups), files, data blocks and files per folder; the zip end record; the 7z start header; RAR version and flags; the ISO volume; the OLE sector layout.
  - New: `.rtf` files are read (text, paragraphs, properties, table rows, picture and footnote counts).
  - A `.docx` with a damaged part is flagged `CORRUPT` instead of `INTERNAL-ERROR`.
- `sigmadeeplook` fix round 11, lane F2 (set 10 miss causes):
  - One pixel of a picture is a lookup: `--ask "RGB colour at pixel x=520, y=600"` answers R,G,B, hex, alpha and palette index, counted from the top-left corner as displayed (bottom-up BMP, palettes, RLE, 24-bit PCX planes, EXIF turns). A pixel outside the picture is answered with the size. The picture print says where to ask (`Ask a pixel`) and gives the size. TGA and Netpbm files are now detected as pictures.
  - A recording with 2 or more channels prints tones per channel (LEFT, RIGHT, channel 3 ...): count, start times, length and background level per frequency. Short pips of 25 ms and up are found. This works for .au, WAV (with or without ffmpeg) and any audio ffmpeg decodes. Before, only the first channel was read.
  - A container with several streams prints a stream table: the container id (PID of a transport stream, track id of an MP4), type, codec, language, channels and bit rate. Every audio stream prints its own steady pitch. Without ffprobe a transport stream's PAT and PMT are read in pure Python, so the PIDs, stream types, languages and the service name are still printed.

## [0.16.5] — 2026-10-23

### Fixed

- `sigmadeeplook` fix round 10, lane F1 (set 9 miss causes):
  - A table inside a text is read from its own header row. A weighing protocol with a title block and a totals block was read as a one-column CSV with 100 reject rows. The title and total lines are now printed whole, and the last 20 rows of every table are printed as the file has them.
  - A legacy Word file with junk in the high half of a stream size lost its text (`CORRUPT: no WordDocument stream`). Version 3 OLE files now ignore those bits, as the format requires.
  - `.ppt` and `.xls` files print their saved properties: application, revision, dates, word and slide counts. Small `.doc` and `.odt` tables print every row. `.odt` footnote and endnote text is printed and kept in `text.md`.
  - A last-record or fixed-position value with no blank in it (a URL, path or key) is no longer cut. A cut feed URL had given a confident wrong answer.
  - New counts: `.po` flag lines per flag; `.properties` and INI keys per prefix; items under each node of a self-nesting XML tree (OPML); each distinct `.sbv`/subtitle line with its cue count when the text repeats.
  - `.properties` values are read as Java reads them: escapes decoded, continued lines joined, escaped separators kept in the key. Latin-1 Spanish (`¿`, `ñ`) is no longer read as Windows-1250.
- `sigmadeeplook` fix round 10, lane F2 (set 9 miss causes):
  - SAS `.sas7bdat` files print their header: dataset name, type, dates, SAS release and host. The header is read without pandas, so a cut-off file still names itself, and its unreadable rows are flagged `CORRUPT`.
  - Every worksheet table (`.xlsx`, `.xlsb`, `.ods`) prints its last row, hidden sheets too. A CSV inside an archive, nested ones too, prints its first and last row.
  - netCDF: a packed variable prints its unpacked values (value x `scale_factor` + `add_offset`) and a grid of the last time step at round indexes, with the coordinate values. Char variables print every entry. A lone record variable is read without padding, and a damaged record count stops at the end of the file.
  - Pictures print every palette entry, the box each frequent colour fills, and a colour gradient as a formula when one fits (for example `R = 255·x/1599, rounded down`). This works with or without numpy.
  - Sound prints tones: stretches where one frequency holds most of the power, with their count, frequency and start times per frequency. A 40 MB file takes under a second.
  - Video prints its key frames from the packet flags: count, first and last time, spacing.
  - A video look with `--quick` printed nothing. Two threads swapped the standard output at once while they imported packages. Imports now take turns.

## [0.16.4] — 2026-10-23

### Fixed

- `sigmadeeplook`: a small zip-based document can no longer eat gigabytes. A 600 KB `.docx` with a 600 MB `docProps/core.xml` took 7.1 GB in the properties reader; a part over 256 MB, or over 16 MB and more than 200 times its packed size, now reads as empty and is flagged `TRUNCATED` (peak 409 MB on the same file). The same limit covers EPUB, OpenDocument and the `--page` pptx reader.
- `sigmadeeplook`: the XML entity guards looked only at the first 200 KB (`parse_xml`) and 1 MB (`xml_entity_danger`) of a file, so a long comment before the DOCTYPE hid a billion-laughs declaration. They now read the whole part. Property parts of office, EPUB and OpenDocument files refuse a declared entity too.
- `sigmadeeplook`: a tool's timeout now ends the whole tool, not only the first process. On Windows a tool behind a `.cmd` shim (diec on a truncated `.exe`) kept running at 100 % CPU and held the output pipe, so the look never returned. `dl_core.run_tree` kills the process tree (`taskkill /T`, a process group elsewhere); the look returns at the limit with a `TIMEOUT` flag.
- `sigmafinanceman` company models run on hosts where FRED does not answer. FRED timed out on every read from three Linux hosts, so every DCF, LBO and comps run failed after two minutes of retries. The 10-year rate now gets one 15-second FRED try, then comes from the Yahoo ^TNX chart (the source column names which one). A test fakes the FRED timeout.
- `sigmafinanceman` `references/masters.md`: the Musk solar quote now stops where the source sentence goes on (no added full stop), and the two Horowitz "calculus" quotes cite the opening of chapter 4, not the section "The Struggle". `references/strategy.md`: the private equity playbook adds buyout lines (debt against EBITDA, the three sources of gain, the exit multiple, fees), next to the venture lines.

## [0.16.3] — 2026-10-23

### Changed

- `sigmafinanceman` carries the investors' knowledge. `references/masters.md` holds ten verbatim, sourced quotes and the core principles of 14 investors and operators (Musk, Buffett, Huang, Ackman, Munger, Jobs, Altman, Bezos, Zuckerberg, Druckenmiller, Horowitz, Leone, Thiel, Andreessen). `references/strategy.md` merges them into one nine-step method for any investment, names where the masters disagree and how the method decides, and gives a playbook per kind (growth and dividend stocks, index funds, macro and trading, private equity and venture, real estate, crypto, a rented-out asset such as GPUs, reselling, cars, buying a business). The question round reads the method first, and `finman.py --principles "Buffett P1,Munger P5"` names the applied principles in the workbook (Method sheet), the deck, the page and the report. A test checks that every quote has a source and a link, and that the skill links both files.

## [0.16.2] — 2026-10-22

### Changed

- Every skill description is 200 characters or less. Fourteen skills were longer (up to 791); each keeps its job, its trigger and its exclusion line. A repository test now fails above 200 characters.
- `sigmadeeplook` `references/office.md`: the legacy `.doc` paragraph list names the fixed positions the code prints (#1-5, 10, 20, 25, 30, 40, 50, 75, 100 and the middle). A test keeps the two in step.

## [0.16.1] — 2026-10-22

### Changed

- `sigmadeeplook` fix round 9 (set 8 miss categories): records at fixed positions (#1-5, 10, 20, 25 ... 100 ... the middle and the last) for text lines, table rows, subtitle cues, `.mo` entries and Word paragraphs; a standard-library reader for legacy Word `.doc` (Word 97-2003, 6 and 95: header, saved properties, paragraphs with heading levels, tables with rows and cells, last paragraphs); exact per-channel sample statistics for Sun `.au`; every `.mo` entry in `text.md`; reST title, fields, tables and code blocks counted.

### Fixed

- `sigmadeeplook`: a `--budget` above 1,000 tokens is now filled with file content (step 1 stopped at a 230-token content cap); semicolon records in Windows-1251 were read as Windows-1252; `.sbv` cues with two text lines were joined into one; a long first fact used as the title lost its end; a damaged `.mo`, `.au` or `.doc` is flagged `CORRUPT`; a looping OLE sector chain no longer reads the same sector again.

## [0.16.0] — 2026-10-22

### Added

- `sigmadeeplook` fix round 8 (set 7 miss categories): the end of the file in step 1 (a `Last row` or `Last lines` fact for tables, text, logs, subtitles and configs); text structure (reST headings of any underline, paragraphs, line starts, directives, frequent words); gettext `.po` and `.mo`, SPSS `.sav`, netCDF classic and Excel `.xlsb` readers; PCX and BMP headers with exact pixel facts; sound bursts (count, times, frequency) for audio and Sun `.au`; MPEG-TS service names; OpenDocument and PowerPoint table rows.

### Changed

- `sigmadeeplook` scripts: seven functions with no caller are gone (`decode_best`, `profile_line`, `collapse_direct`, `md_table`, `need_tool`, `mail_ics`, `scenes_list`), and `safe_extract` uses one copy helper for zip and tar members. No behaviour change.

### Fixed

- `sigmadeeplook`: SAS text columns were counted as `<8 bytes>` (a wrong distinct count); a legacy code page was printed as replacement characters in the whole-file block; a partial head view is now marked `PARTIAL`.

## [0.15.2] — 2026-10-21

### Changed

- `sigmaloop`, `sigmabrief`, `sigmaship`: the Claude Code run mode. A `/goal` line names one printed command that proves the end state. The loop file is the run file, read every turn. Dated items are `CronCreate` tasks, and a handoff file is rewritten before each long wait. `sigmaloop`'s Claude Code host file, loop-file template and stop-line question carry it. A `sigmabrief` session brief and a `sigmaship` run point at it (ticket 83, GL4).

## [0.15.1] — 2026-10-21

### Fixed

- `sigmadeeplook --ask`: a question with two numeric words (such as "how many tool errors") no longer takes a column that names only one of them. `hookErrors` and `shape.tools` no longer answer it. The look now says no table answers exactly, and it shows the matching lines (ticket 83, K29a-1).

## [0.15.0] — 2026-10-21

### Added
- `sigmafinanceman` (SigmaFinanceMan): the finance analyst. `scripts/finman.py` reads SEC EDGAR company facts (10-K and 10-Q), Yahoo chart prices and the FRED 10-year yield, and builds a DCF, an LBO, trading comps, a three-statement model, ratios, a statement analysis with red flags (Sloan accruals, Altman Z, Piotroski F), a ten-test value scorecard, an earnings review and a personal 50/30/20 budget. Each run writes an Excel workbook with live formulas in banker colours (inputs with source comments, a Checks sheet), a 16:9 deck with native charts, SVG charts and one HTML page in the Ledger look. `audit` recalculates a workbook in LibreOffice and lists formula errors and checks; `selftest` runs offline. Folds in the methods of anthropics/financial-services (Apache-2.0) and the open finance skills listed in `references/sources.md`.

### Changed
- `sigmaship`, `sigmabrief`, `sigmareview`, `sigmaresearch`, `code-review` and `research`: prior-art search before a build (SigmaShip), three questions and a sub-agent honesty rule in every brief, bugs-only review wording, and a critic pass on big research (ticket 83 K29a-3, K29a-4, K29a-14, K29a-16, K29a-21).

- `sigmaresearch` X search: when an xAI route with the `x_search` tool exists, Grok lists post URLs first and each one is read in full by URL. Grok cannot open one post by URL, so a Grok answer counts as a lead only.

## [0.14.0] — 2026-10-20

### Added

- `sigmatour` (SigmaTour): a visual 15-60 minute tour of any repository in one HTML page. `scripts/sigmatour.py` (standard library) measures the repo without writing to it: size, languages, folder tree, history, entry points (package scripts and bins, console scripts, Makefile targets, main files, Dockerfiles), tests and CI, and the README held against the repo (commands with no script or file behind them, paths that do not exist, environment variables the code reads that no doc names, scripts and top folders the README never mentions, TODO and FIXME notes). `build` writes that into `assets/tour-template.html`, which draws the numbers band, the folder explorer, the history band, the README check and the entry points; the agent adds the transit map, the architecture figure, a stepper that follows one real request file by file, examples run for real, the hidden and missing list and the deep dives that set the length. `check` lists what is left. Plain technical English in the `/sigmawrite` voice.
- `sigmaresearch`: Reddit and X never end at a block. The Reddit reader reads a thread's post and full comment tree from the Arctic Shift archive when JSON is blocked (401 login wall or 403 network policy), and searches titles there inside a subreddit; a removed archive copy takes its body from the live feed. The HTTP core follows a host's own window (`x-ratelimit-remaining`, `x-ratelimit-reset`): the Reddit feed allows one read per minute, so the next read waits for the reset instead of failing. `read.py x <post URL>` reads a post without a login (the FxTwitter API, then X's embed JSON) with its likes and reply count; a browser dump is filtered by the query words, so off-topic posts never reach the answer. `references/reddit.md` and `references/x.md` give the full route order: the reader's routes, a real browser (also a stealth Chromium on a server), another network address, more archives; tested on three threads and three posts.
- SigmaHuman follows blader/humanizer upstream: a vendored copy (`sigmahuman/upstream/humanizer-SKILL.md`, commit and version in `UPSTREAM.json`) and one update command, `python sigmahuman/scripts/upstream.py status | sync [--ref R] | check`. `sync` rewrites the 26 patterns, the licence and the version lines and lists upstream's other changes for our layer; `check` runs in `npm test`. Lanes, section G, the write mode and `factcheck.py` stay ours.

### Changed

- Sigma Installer: the owner's studio folder preset is now the generic `local` pack (`--preset local`, alias `own`, folder from `SIGMA_LOCAL_SKILLS_DIR` or `dirs.local` in `~/.sigmaskills/packs.json`, no id prefix). A named pack with a prefix goes into `~/.sigmaskills/packs.json` under `packs`.
- The public package names no private repository, host or path any more: `DESIGN.md` (now Black-Green), `AGENTS.md`, the installer guide, the arena template, the deeplook tests (real files from `SIGMADEEPLOOK_REAL`, else `~/.cache/sigmadeeplook/real`) and the guardrail lint. A repo invariant fails when one comes back. Tracked `__pycache__` files are gone.

## [0.13.0] — 2026-10-20

### Changed

- `sigmafork`: the onboarding course v2 (ticket 83 P13.75, the owner's verdict on v1: one good graphic, too little explained, hard to read, not his look). The template now wears the Storge-Black-Green look of `DESIGN.md` (zinc canvas, green glow, one emerald, Inter) and has 10 stops with at least 6 figures: the transit map is clickable (each stop shows its folder with its numbers, the file to open first and the command), a numbers band and language bar, a folder explorer (folders sized by code lines, tap to go in), the use case as a strip of real frames ("One job, start to finish"), map line cards, a change-flow strip, and a copy-and-original figure. Check-yourself questions are quizzes, tasks are tick boxes, the cheat sheet has a filter, terms explain themselves on tap. Code blocks get a header so the Copy button never covers a command. `references/guide.md` sets the `/sigmawrite` voice: one lead line per stop, three sentences a paragraph at most, commands in code blocks.

### Added

- `sigmafork.py stats` counts what a repo really holds: files, folders, code lines without blank and comment lines, doc lines, languages, the biggest code files. It leaves out installed dependencies, build output, caches, venvs and generated files (lock files, minified bundles, "do not edit" headers) and says how much it left out.
- `sigmafork.py guide` makes `ONBOARDING.html` from the template and writes the stats, the folder tree and the copy facts (`copy.json`, `paths.json`, `verify`) into its data block, from which the page draws its numbers. `guide --check` lists what is still wrong: `FILL` left or no data (exit 1), long paragraphs, chip-heavy text, terms without a meaning and too few figures (fixes).

## [0.12.0] — 2026-10-20

### Fixed

- Sigma Installer: `--agent agy` (Antigravity CLI) now installs global skills to `~/.gemini/config/skills`, the only folder `agy` 1.4.2 reads (probe skills in `~/.gemini/antigravity-cli/skills` and `~/.gemini/skills` were not listed). The override sits in `src/destinations.js`, so `registry:sync` cannot undo it. A link method is invisible to `agy` (a Windows junction listed no skills, the same folder as a copy did), so `install --agent agy` writes a copy unless you pass `--link`. In the wizard press `m` for Copy.

### Added

- `sigmafork` (SigmaFork): fork or copy any repository, from GitHub or a local folder, and onboard the owner. One grill round of 8 questions with a recommended answer each (what, why, where the resources are, research depth, skill bundle, where it goes, access, how he learns best), a study of the source with `/sigmaresearch` at the chosen depth, then the fork, clone or copy. `scripts/sigmafork.py` (standard library) copies a folder without installed dependencies or caches, remakes links that point inside the source so they point inside the copy, rewrites every spelling of the source path (`C:\x`, `C:/x`, escaped, Git Bash, WSL, `file:///`) byte for byte, lists other outside paths and git remotes, and `verify` prints `ISOLATED` only when nothing in the copy reaches the original. The owner types every login and key himself. It installs the chosen skill bundle, writes `ONBOARDING.html` (a 10-15 minute course from `assets/guide-template.html`: the repo as a transit map, real example projects, first three tasks, cheat sheet), and turns the owner's questions into part 2 with the top 3 resources.
- `sigmadesign` (SigmaDesign): make a design system end to end from one accent colour, then apply it and integrate it across a repo. `scripts/sigmadesign.py` (standard library) writes `DESIGN.md` in the Google Stitch format (dark tokens, `light-*` tokens, type scale, corners, spacing, components, a prose skeleton), adds colour packs (`pack`, dark or light, any accent; the tool moves the accent until text and accent pass WCAG AA), builds `tokens.css`, a Tailwind 4 `@theme inline` map, `components.css` and a sample page with a theme switch, and `check` fails on a low-contrast pair or a stale build. `scan` lists every hard-coded colour with its nearest token and rewrites exact matches in CSS; `integrate` copies `DESIGN.md` into a repo byte for byte and adds one pointer line to `AGENTS.md` and `CLAUDE.md`. The card asks one round of 6 questions with a recommended answer each and links three references: the file format, the repo steps, and the looking checklist (375 and 1440 px, every theme). Built from the Storge look (ticket 83 P13.49): the same generator reproduces its dark palette from one accent.
- Sigma Installer: **packs and presets.** `--preset sigma|mattpocock|threejs|hyperframes|minimax-h3|storgestudio|all` installs a whole pack (repeatable or comma-separated). The five outside packs ship as a snapshot in `registry/packs.json` and download from their GitHub repositories at install time; `~/.sigmaskills/packs.json` adds your own packs and points the StorgeStudio folder pack at a folder. Pack skills install to `.agents/skills/<id>` with links or copies into host folders, with a private ownership record, and `update`, `uninstall` and `status` cover them. A copy you edited stays until `--force`, which backs it up first. `list --packs` shows every pack.
- Sigma Installer: **`--agent` / `-a`** names Agent Hosts (`claude`, `codex`, `gemini`, `agy`, `pi`, `cursor`, any registry id, or `*`). Hosts that read `.agents/skills` need no folder; `--agent claude` adds `.claude/skills`. An unknown name suggests the closest ids.
- Sigma Installer: **a full-screen wizard** for color terminals: What (packs with counts, open a pack to pick single skills, `/` filter, number keys), Where (scope, Agent Hosts with the found ones marked, Link or Copy), Review (counts, destinations, downloads, conflict choice, an explicit `y` for Global), then progress and a clean summary by pack. `--classic` keeps the line-by-line installer, which also serves plain, static, CI, JSON and piped sessions.
- `--force` (pack skills), `--classic`, `--packs`. README screenshots, `docs/images/`, and `scripts/capture-installer.js` to refresh them.
- ADR 0007 records the decision; CONTEXT.md gains Pack and Wizard.

### Changed

- Sigma Installer: the terminal palette is the DESIGN.md palette (near-black canvas, one emerald accent) in both installers. The warm Emberforge colors are gone.
- Sigma Installer: install, update and uninstall of several skills with `--preset` or `--agent` print one summary (counts, packs, destinations, what was kept and why). A plain `install <id>` or `install --all` keeps its old output.

## [0.11.0] — 2026-10-20

### Added

- `sigmahuman` (SigmaHuman): makes any text read like a person wrote it. Two modes: Rewrite (text, a file or another skill's output in, the human version out) and Write (a brief in, new text out). Seven lanes in `references/lanes.md`: Ear (a script for the ear: keep the narrator's sentence-length band), Book, Song (meter, rhyme, the hook), Chat (lead with the answer), Docs, Post and Brief. Voice matching from a writing sample. Facts come from the source only: a missing detail is asked for or written around, never invented. A pipeline pass mode edits a set of files once and the caller takes the result as written. The 26 patterns are [blader/humanizer](https://github.com/blader/humanizer) v3.1.0 unchanged (MIT, Siqi Chen; notice in `references/LICENSE-humanizer.txt`), plus five tells from its v2.5.1 copy. `scripts/factcheck.py` compares numbers (digits and number words), quotes, inline code, links, names and the sentence-length band before and after a rewrite.

### Changed

- `sigmaresearch`: the merge conflict in `SKILL.md` is gone and the freedom side stays; the model-written bans (never log in, stop on 403 or 429, no mirrors) are deleted from the card and its references. New persistence ladder in the card, "Keep going until the answer is found": name the target, walk the routes, keep a route list (it goes under `## Access gaps`), retry a 429 slower with backoff, take another route when a login wall, paywall, CAPTCHA or bot check closes one (solving the check is not a route), widen the query, and stop only when a second source agrees or every fitting route is listed. New `references/deep-routes.md`: site feeds, sitemaps and the JSON a page loads, Wayback, archive.today, Common Crawl, search operators, PDFs, filings and transcripts, GitHub code and issue search, Hacker News Algolia, Reddit JSON, RSS and archives, academic indexes, other languages, and the owner's signed-in Chrome as a reading route on any site.
- `sigmaloop`: one portable card, one host file per host. `references/hosts.md` is now a table (loop mechanism, clock wake, headless run, skill folder) and the plain instruction; `host-claude-code.md`, `host-codex.md`, `host-antigravity.md`, `host-pi.md` and `host-t3-code.md` hold each host's facts, each marked run, doc or source, and the prompt skeleton. New: Antigravity `agy` (`/goal`, `/schedule`, Stop hook), the lapi plan-file loop for pi (a `lapi-workflow` box fence, or nothing loops), T3 Code's `schedule_task` tool (the old card said it had no scheduler), headless runs (`claude -p "/goal"`, `agy -p "/goal"`, a Codex `Stop` hook; `codex exec` does not expand `/goal`, and `claude -p "/loop"` runs once), and the Git Bash path rewrite of a leading `/word` on Windows.


### Added

- `sigmataste`: three wait-what checks beside the lenses, in `references/wait-what.md`. Glossary in sync (words the project uses that its glossary lacks, one word with two meanings), glossary current (entries nothing uses, or whose meaning drifted, each with update, merge, retire or delete and a reason), and the target against the repo's `DESIGN.md` when it is a UI. They never block, use judgment instead of fixed rules, move or delete nothing, and end in a "Wait-what fixes" section of the plan for the calling agent to apply.

- `sigmadeeplook`: dBASE / FoxPro `.dbf` tables are detected by structure and decoded (record count, fields and types, language driver, deleted records, truncation), then profiled like a CSV. Container counts for audio files from the bytes alone (Ogg pages, packets, streams, codec and duration; WAV chunks; FLAC blocks; MP3 frames). Element values by path over the whole XML document in the first print, and the same for XML members of zip-based formats, including single-line ones (Visio-style pages).

### Changed

- `sigmadeeplook`: when the header detector finds no signature but a content model (Magika) or `file -b` names a type, the reader for that type runs instead of an unknown-type exit 3. A headerless fixed-record guess no longer exits 3. A complete small look says so once and lists only the drill-down flags it offers.

### Fixed

- `sigmadeeplook`: wrong answers stated as certain. A CSV past the 256 MB read limit no longer prints "Every row was read; a full pass": it says how many bytes were read, counts the lines of the whole file in bounded memory, and marks every figure `PARTIAL`. JSON past 64 MB and XML past 20 MB are parsed as far as the limit (complete elements kept) and flagged `PARTIAL`, not called invalid. A harmless `<!ENTITY>` declaration no longer refuses an XML file; only a self-referring or exploding entity does. The formula evaluator is a real parser with Excel's rules (`2^3^2` is 64, `-2^2` is 4, `&` joins text, text compares without regard to case, huge powers are not evaluated) and no longer calls a value "evaluated, not guessed" when it is not sure: it names the formulas it did not compute. Text that is not UTF-8 is read with the code page whose letters look real (Windows-1250 for Serbian Latin, Windows-1251 and KOI8-R for Cyrillic, Greek, Turkish, Windows-1252), and one stray byte no longer turns a UTF-8 file into Windows-1252. The cache key of a file over 8 MB is a bounded sample plus size and modified time, so `--more` and `--ask` no longer re-read a 20 GB file.

- `sigmadeeplook`: more of the H6 review. `--ask` reads a table through a stream with a row and cell budget (CSV, JSON Lines, SQLite and Parquet no longer load whole), says PARTIAL with both counts when it stops early, and names a table it could not read. Its question words are one table for English, German and Serbian/Croatian (Latin or Cyrillic, accents folded): operations, `per X`, comparisons, `first` / `last` rows; "at most 5" is a comparison, and "how many ... total weight" is a sum whenever a numeric column is named, not only for a fixed list of nouns. The archive screen refuses the whole archive only for hostile names, links that leave it, overlaps and deep nesting; a relative link inside the archive, a duplicate name, a Windows-reserved name or one high-ratio member now leave out only that member, and too many members or bytes refuse `--extract` only. A compressed tar listing stops at a time cap and says PARTIAL. A headerless binary table is also tried after a header (the offset is found, the runner-up layouts are named), and its date window is 1990-2100. Claim, section-turn, stated-total and front/back-matter words exist for German and Serbian next to English (`dl_lex.py`); a book with a conclusion or epilogue prints its chapter count both ways. Torrent, plist, MIDI, pyc, TOML and `--func` name a file past their size limit instead of loading it, a `.deb` is mapped instead of read, and `--lines` streams. Syslog lines without a year take it from the file's modified time and roll back across a new year. A `.torrent`, `.dta` or binary STL is typed only after its first bytes check out. The token estimate counts accented, Cyrillic and Greek letters at about 2.5 characters per token.

## [0.10.0] — 2026-10-19

### Added

- `sigmaloop` (SigmaLoop): reads a repo's open work, asks one dense round of questions (host, end time, order, crew and model mix, off-limits, pre-authorised actions, landing, stop line), then writes a paste-ready loop prompt for Claude Code `/loop`, Codex `/goal`, pi plan mode, T3 Code or a plain instruction, plus a loop file the prompt tells the agent to re-read at every wake. It never starts the loop.
- `sigmataste` (SigmaTaste): looks at a page, app, deck, doc, image or film, asks one round of at most 10 questions (which of 14 taste lenses, what the owner expects, scope, brand, constraints), then writes `sigmataste-plan-DD-MM-YYYY.md` with the changes that make a big visible difference, ranked, each with a verify step, and stops. The lenses are fitted from the taste, design and writing skills in claude-skills-collection, credited in `references/sources.md`.

### Changed

- `sigmaship`: audited against today's ship flow. It never checks out, resets or commits in a shared main checkout, names known reds instead of fixing them, merges with `--match-head-commit`, removes the worktree before the branches, syncs main with `fetch` + `merge --ff-only`, proves deploys live, ticks the tracker with the PR number, syncs docs, and uses an own-diff check as the review round when sub-agents are not allowed. The checkout + pull steps and the always-stop red baseline are gone (#116).

### Fixed

- `sigmafreedom`: `scripts/guardrail_lint.py` held raw backspace bytes where the owner regex has `\b` word boundaries (a heredoc ate the backslashes), so owner-attributed lines were not exempt. The bytes are `\b` again, and a test keeps every shipped Python file free of control bytes.

## [0.9.2] — 2026-10-18

### Fixed

- `sigmadeeplook` readers from the held-out rounds: binaries, archives, tables and spreadsheets read more fields correctly (typed binary fields, VBA source, `.reg`, `.deb` members, list columns, MIDI events, docx Title) (#111, #112). The headerless-records test now skips when numpy is missing, which turns the main branch CI green again.

## [0.9.1] — 2026-10-18

### Fixed

- `sigmacreatearena`, `sigmaresearch` and `sigmawritegui` had a plain YAML description containing `: `, which strict YAML parsers reject. The descriptions are now quoted, the installer reads quoted values as plain text, and a test keeps every header strict YAML.

## [0.9.0] — 2026-10-18

### Changed

- `easytalk` is renamed `sigmawritegui`: SigmaWrite plus a GUI board the user reads and types into. The trigger phrase "easy talk" and the `EASYTALK REPLY` format stay.
- `storgestudio-arena-create` is renamed `sigmacreatearena`.

### Added

- `sigmafreedom`: de-safeguards and decensors any repository. Writes the freedom doctrine into the steering docs, sweeps agent-facing docs and skill sources with a classifier (freedom limits and moral voice deleted with a was/now change log; craft, scope-routing and mechanical lines kept), installs `guardrail_lint` with an owner-vetoable allowlist wired into the repo's gate plus a negative self-test, writes the ADRs, and reports the kept-list for the owner's veto.

## [0.8.0] — 2026-10-17

### Added

- `sigmadeeplook` (SigmaDeepLook): the helper for what an agent cannot read with its own tools: video, audio and speech, scanned PDFs and images, Office files with hidden parts, SQLite, Parquet, binaries, archives, fonts and 3D. One standard-library Python entry (`scripts/look.py`) gates every file first: plain text, CSV, JSON and code go back to the agent (`READ`); the rest gets a look in about 1,000 tokens, `--more` for the next part of the same stream, and `--ask "<question>"` for one exact, checkable answer from the stored look. Runs on a bare Python install (most document types and media facts); every missing tool (ffmpeg, Whisper, tesseract) becomes a Not-looked-at row with its install line. Never runs the input, no network unless `--allow-network`, refuses unsafe archives, keeps private values out of the summary. Measured (ticket 83, 2026-10-17): on 5 media files and 38 questions, Haiku with deeplook matched plain Haiku (38/38) at 43 % lower cost and 29 % fewer turns.
- `.gitignore` ignores `__pycache__/`.

## [0.7.0] — 2026-10-15

### Fixed

- `sigmaresearch` Reddit reader: a search hit counts only if its title or text holds every query term (or quoted phrase), and the count of dropped items is reported as a gap and in `stats.dropped`. Thread URLs read `<thread>.rss` and report `BLOCKED` when no route loads. Items without a date rank below dated items. (#101)

### Added

- `sigmaresearch`: an **access ladder** for every URL (public JSON, RSS or Atom, old or lite HTML, official API, archive mirror, the host's browser, the owner's browser session, video subtitles or audio with speech-to-text), in `references/access-ladder.md`. When a rung is blocked, the skill takes the next one and logs which rung worked, instead of giving up on a reachable platform. Pages in another language are fetched in the original, translated inline, with the original quote and URL kept. The Reddit reference records the 2026-10-15 test.
- `sigmaresearch`: **counting rules** for depth (`references/counting.md`). A source is one unique page read in full; snippets and digests count 0; the same URL counts once; at most `per` count per meta source (a site or platform family taken from the URL). A source-log contract (`N. meta source | URL | date | language | read=full|digest | words read | takeaway`) and `scripts/source_log.py`, which counts logs against plan words (`meta= per= full= split= must=`) and exits 1 when the plan is not met. Tests in `test/sigmaresearch.test.js`.
- `sigmaresearch` v2: bundled stdlib Python readers behind one interface (`scripts/read.py <platform> <query|url> [--limit N] [--json]`) for Reddit (JSON, then RSS, then a search-engine or archive fallback), Hacker News, GitHub, Stack Overflow and YouTube comments, plus a normalizer for X text copied from the owner's signed-in Chrome. Adds parallel fetch with per-host rate limits and bounded 429 backoff, a 24-hour cache in `~/.cache/sigmaresearch`, source scoring (votes, recency, independence), a Contradictions section in the report, a depth and early-stop rule, and `read.py selftest`. Blocked hosts are reported, never bypassed. (#99)
- `storgestudio-arena-create`: optional reference media per group (`refs`). The page shows them as thumbnails sized by the window. Click one for full size, `←`/`→` for the next, `R` for all in a grid; `F`/`G` show them in a column beside the option. Optional `anchors` (reference players): they get a rating but never take a top-K place, and after `settings.anchor_games` games (default 8) their pairs get ×0.1 weight. The self-test covers both.

### Changed

- `sigmaresearch`: after a 403, a login wall or a bot check the skill no longer stops at the platform's own fallback: it takes the next rung of the access ladder, another normal public way to read the same page. A 429 means wait 45 to 60 seconds and retry that URL once (the bundled reader keeps its two bounded retries). It still never logs in, solves a CAPTCHA, uses cookies or tokens, or gets past a paywall. The default depth line now points to the counting rules.
- `storgestudio-arena-create`: the metric row keys go by key position (`e.code`), so QWERTZ and QWERTY both work (`Q W E`, `A S D`, `Y X C`/`Z X C`, `U I O`, `J K L`). The arrows no longer vote; they move between references. The page uses the full window width.

## [0.6.1] — 2026-10-06

### Changed

- A changed front-matter `description` in `SKILL.md` now counts as a Skill Customization. `status` reports it as `valid-customization`, not as corruption. `update --yes` keeps your description when it installs a new Release. If the new Release changes the description itself, `update` still asks for `--outside-edit` first. (#94)

## [0.6.0] — 2026-10-06

### Added

- `storgestudio-arena-create` (Arena Create) builds a blind-pairs arena so a user ranks any options by Elo per metric: models, voices, captions, thumbnails, outfits. It grills first, then copies a bundled kit (stdlib Python server and one HTML page, no install) and reads the board back with ranges and costs. Install it from repository source until the next Release.
- `easytalk` brings plain chat and interactive status or question boards to any project. It includes read ticks, recommended options, task statuses, free text, keyboard controls, and copied replies that name every unread card. The self-contained HTML template works with an Artifact tool or a local browser file. (#89)
- `sigmaresearch` (SigmaResearch) is a portable general research skill for Reddit, X, Hacker News, GitHub and Hugging Face. It carries the Reddit RSS and owner-session Chrome recipes tested on 2026-10-04, records source dates and read scope, and reports access gaps. It never logs in or evades bot checks, and stops platform access on 403/429. (#90)

### Changed

- No bot opens recurring pull requests any more. Dependabot is gone, because its pin bumps always failed CI: the tests compare the action pins with constants in the release scripts. The action pins are now checked as a step before each Release. The Agent Host registry sync no longer runs every day; it runs on demand as the first step of a Release, and both of its inputs are optional.
- The release, registry-sync, and rehearsal jobs run on the latest Node.js 24 LTS (`node-version: '24'`) instead of one fixed patch, so that pin never goes stale.

## [0.5.1] — 2026-09-30

### Fixed

- A crafted skill name in `state.json` or the Sigma `skills-lock.json` (such as `../../victim`) is now rejected when the file loads. Before, `uninstall --all` could use it to delete a folder outside the project while pruning backups. Backup commit and prune also check that they stay inside the backups folder. (#84)
- `restore` rejects a backup whose metadata lists owned paths or a link dependency outside the project or home folder, before any write. Before, such a backup was restored and left `state.json` unreadable for every later command. (#84)
- `uninstall` and `restore` now print the notice that `skills-lock.json` was left alone when another tool owns it, as `install` already did. (#84)
- A resumed `purge` journal is checked for every recorded path, including the quarantine path and link target. A crafted journal can no longer make rollback remove or move a folder outside the project. (#86)
- The release preview no longer prints expected "not found" errors from npm, GitHub, and git to the terminal.
- Applying a registry patch Release no longer puts the new version heading after the wrong section when `[Unreleased]` is empty. The next owner Release would have failed with an identity mismatch. (#85)
- Running `release --write-identities` again on a prepared candidate no longer adds a second, self-comparing `[X]` compare link. (#85)
- The registry path check now rejects protected locations written as `.github//workflows`, `.github/./workflows`, or `.git.` and `.git ` (Windows ignores trailing dots and spaces). (#85)
- The owner Release checks (npm, GitHub Release, environment, git tag) count only a real "not found" as absent, and any other error stops the Release. Tag creation ignores only an "already exists" error. (#85)

### Changed

- The install transaction, the interactive installer, and the release tool are split into smaller named steps and modules. Behavior is unchanged. (#81, #82, #83)
- The release preview docs say which changelog entries count as breaking before 1.0.0. (#85)
- SigmaShip now says to use the shell native to the executing machine, and to use `/tdd` when it is installed. Its `land.md` commands are shell-neutral. (#85)
- The bug template no longer shows an old version number as the CLI version placeholder. (#85)

## [0.5.0] — 2026-09-29

### Added

- The 2026-09-29 full audit of 0.4.0 is kept in `docs/audits/AUDIT-2026-09-29.md`. (#71)

### Changed

- CI and release jobs use current actions and Node.js. `actions/checkout` is v7.0.1 and `actions/setup-node` is v7.0.0, both pinned by full SHA. The release, registry-sync, and rehearsal jobs run on Node.js 24.21.0, whose bundled npm 11.19 supports trusted publishing, so the extra `npm install -g npm@11.5.1` step is gone. The `package-manager-cache: false` setting is now a valid input, and the runner no longer warns about Node 20 actions. (#69)
- `.github/dependabot.yml` opens one weekly pull request to keep the `github-actions` pins current. (#69)
- The bug template has a "Sigma Installer (CLI)" area and optional fields for CLI version, Node.js version, and OS. The pull request template adds `npm test` and CHANGELOG checkboxes and covers the CLI. Every job in `release.yml` and `registry-sync.yml` has `timeout-minutes: 30`. (#69)
- The six skills now agree with each other. SigmaShip and SigmaBrief both merge the base branch into a pushed branch (no rebase), use `<base>` (default `main`), delete a squash-merged branch with `git branch -D` only after the PR shows merged, define P1 as SigmaReview does, and use the shell native to the executing machine. In a SigmaShip review round, the `CLEAN | FIXED | BLOCKED` report wins over SigmaBrief's format. The grilling skill is called `/grilling` everywhere. SigmaShip says to write the acceptance criteria by hand when `/to-spec`, `/to-tickets`, or `/grilling` are missing. The README lists these optional companion skills from `mattpocock/skills`. (#65)
- SigmaBrief examples now use its own dispatch format and generic content. (#65)
- SigmaRefactor and the README no longer name a private repository, and they say `laloc` is optional. (#65)
- Tests check that `openai.yaml` lists only Codex products (`chatgpt`, `codex`, `atlas`), that every skill name and description follows the Agent Skills limits, and that every relative link and `#anchor` in the skill folders resolves. (#65)
- Package metadata: `package.json` now has `license` (`MIT`), `bugs`, and `keywords`, so npm shows the license. (#64)
- Docs and changelog match 0.4.0. The CHANGELOG compare links and the 0.4.0 package-size note are fixed, 0.2.1 is marked as a GitHub Release only, and the 0.2.0 sections follow Keep a Changelog order. The installer guide now covers the Link/Copy page, the `a` key, plain mode with `TERM=dumb` and `--json`, Escape in the destination search, and the hidden aliases (`-g`, `--cwd`, `--list`, `check`). The maintainer guide covers `registry:sync`, `registry:validate`, and the role of `.agents/skills` and `skills-lock.json`. ADRs 0005 and 0006 and the wayfinder label note are corrected. (#64)
- The Agent Host registry follows `vercel-labs/skills` at `2a286c7`: Pi is now a universal host that reads `.agents/skills` (project) and `~/.agents/skills` (global) instead of `.pi/skills` and `~/.pi/agent/skills`. Existing installs keep their recorded paths. (#78)
- The generated registry pull request no longer says it "may auto-merge". It says auto-merge only runs when `main` is protected with required checks, and the owner merges by hand otherwise. `main` is not protected, so registry sync pull requests are reviewed and merged by hand. The maintainer guide says so, and ADR 0004 has a status note. (#70)

### Removed

- **BREAKING CHANGE:** Node.js 20 is no longer supported. `package.json` `engines.node` is now `>=22`, and CI no longer runs a Node.js 20 job. Use Node.js 22 or newer. (#70)
- A private homelab plan that did not belong to this project (`.cursor/plans/`). `.cursor/` is now ignored. (#64)
- Signal handlers in the install transaction that could never run, the unused `MIGRATABLE_KINDS` list, a `keypress` `removeListener` call that removed nothing, and the lossy `injectCustomContent` helper. (#67)

### Fixed

- `npm run release` works on Windows when Git Bash's `tar` comes first on `PATH`. It lists the tarball by file name inside its folder, because GNU tar reads `C:` in a path as a remote host. It also starts npm through Node instead of a shell, so Node no longer prints the DEP0190 warning.
- The README no longer claims that every GitHub Release is on npm, and its run section names only real hosts.
- The release tool keeps release notes exactly as written. Notes with `$&`, `$'`, or `` $` `` are no longer changed when the version is applied, and a changelog with only `## [Unreleased]` now gets its version heading. (#68)
- Applying a release now adds the new compare link (`[X.Y.Z]: …/compare/vPREV...vX.Y.Z`) and moves `[Unreleased]` to compare from the new tag. The registry patch release does the same. (#68)
- A registry patch Release now puts its version heading after the whole `[Unreleased]` section. Before, it went right under `## [Unreleased]`, so the owner's unreleased notes ended up under the patch version. (#70)
- A `.sigma.lock.guard` folder left by a hard kill is now detected. When it is older than one minute, the command stops with a `lock-guard-stale` error that names the folder and says to stop all SigmaSkills processes and remove it. Before, every run failed with a bare `lock-busy` message. The installer does not delete the folder itself, because two processes could both decide it is stale. (#70)
- The auto-merge check now says no when any required input is missing (head SHA, generated SHA, expected SHA, default-branch SHA, check result, or classification) or when a SHA is not 40-hex. Before, a missing input skipped its check. (#68)
- Registry automation stops when a `gh`, `npm`, or `git` lookup fails for any reason other than "not found". Before, a network error counted as "no npm versions", "no concurrent run", or "no release", so a version could be reused. (#68)
- `npm run registry:sync -- --dry-run` now writes nothing, including with `--fetch` (it used to overwrite the fixture). The dead `fetchPinnedSourceSync` branch is gone. Registry validation rejects destinations under `.git`, `.github/workflows`, and `.ssh`, so a new host with such a path needs owner review. (#68)
- `agents/openai.yaml` no longer lists the invalid product `api` in any skill. Codex could ignore a metadata file with an unknown product. (#65)
- SigmaBrief now sets `allow_implicit_invocation: false`, so the host no longer starts it on its own. (#65)
- Two broken `measure.md` links in `sigmareview/references/method.md` now resolve. (#65)
- The migration error message, its comments, and the installer guide now name 0.3.0 as the last version with the old state layout. 0.4.0 already uses the new layout, so the old advice to run `@0.4.0` failed in the same place. (#64)
- The README host list names only hosts that exist in the registry. (#64)
- A project `skills-lock.json` from another tool is never rewritten. When the file is a generic (non-Sigma) lock, `install`, `uninstall`, and `restore` leave it byte-identical, print a notice, and still finish the install, uninstall, or restore. The Sigma lock is only written when the file is missing or already a Sigma lock. (#66)
- State and purge-journal paths that escape the project, home, or state folder are rejected when they load, with an error that says the path "escapes" its folder. A crafted `../victim` destination in `state.json` can no longer make `uninstall` or `purge` delete a folder outside the project. (#66)
- `restore` now stops with `occupied-unowned` when a recorded host destination (for example `.claude/skills/<skill>`) holds files Sigma does not own. Before, it deleted those files and put the skill there. (#66)
- A foreign `.agents/state.json` or `.agents/backups/` from another tool is no longer moved into the private folder or removed. Those two names count as Sigma's old layout only beside a `state.json` that has Sigma's shape. `install` no longer fails on such a project. (#66)
- Reinstalling over a Sigma-owned link that points to the wrong target now stops with a `wrong-target` error. Before, it printed "Installed" with exit code 0 and left the wrong link in place. (#66)
- `status`, `update`, and `uninstall` now classify a link that a user added inside a skill the same way, as a local addition. They share one tree walker. Before, `status` and `uninstall` called such a skill clean while `update` called it changed. (#66)
- `--adopt-* replace` and `--adopt-* export` over a junction or symlink now work. The backup or export holds the folder the link points to, and the backup passes the integrity check. Before, both failed with `EEXIST`. (#66)
- A project `skills-lock.json` with a newer `schemaVersion` than Sigma supports now stops the command with an error. Before, Sigma read it as version 1 and wrote it back without the newer fields. (#67)
- Replacing a changed skill (`--adopt-* replace`, `update --outside-edit replace`) keeps the customization block byte for byte. A block that began with a Windows line ending lost one byte before. (#67)
- A destination folder whose name starts with two dots, such as `..cache/skills`, is accepted. `..`, `../x`, and absolute paths that leave the project or home are still rejected. One shared check now does this everywhere. (#67)
- `restore` rejects a backup whose metadata names a `canonicalTarget` or a copy destination outside the project or home folder. (#67)
- The install lock is released when setup code fails right after the lock is taken. Before, a failure there left the lock behind until its owner stopped. (#67)
- `CI=false` and `CI=0` now mean "not CI" in the interactive installer, the same as in the `purge` check. (#67)
- When `update` fails on a later skill, it still lists the skills it already updated after the error message. (#67)

## [0.4.0] — 2026-09-27

### Added

- SigmaImprove (`sigmaimprove`) finds what would make a product, game, codebase, or system clearly better. It scans a full list of improvement categories (value, speed, control, look and feel, reach, intelligence, trust, engineering, and games) and compares the product with the world's top one to three products and with published bars such as Core Web Vitals and WCAG 2.2. It keeps at least ten entries: ideas with 3–5 weighed options and text sketches, and signals that flag a gap for a person to think about. It files one living issue per category (1–20 per run) and updates those issues on later runs instead of duplicating them. It never edits the system. It grew out of the SigmaCheck draft, which was never released.
- The first SigmaCheck audit of this repository is kept in `docs/audits/SIGMACHECK-2026-09-26.md` as a baseline.
- SigmaShip (`sigmaship`) ships one planned GitHub issue end to end: a feature worktree and branch, a draft PR linked to the ticket, spec, and map, test-first commits pushed as it goes, review rounds by fresh agents until one finds nothing at P0–P2, then merge, ticket closed, branches and worktree deleted, and local `main` verified equal to `origin/main`. It refuses tickets without checkable acceptance criteria and names the skill to run first. It builds on Matt Pocock's `implement` skill.
- `install` takes several skill ids (`install sigmawrite sigmareview`) or `--all`. Every skill is planned first, then all of them install in one transaction: if one fails, none stay installed, and `skills-lock.json` is written once. `--json` prints `{ schemaVersion, plans }` when there is more than one skill; one skill prints the same plan as before. (#38)
- Skill evals. `npm test` now checks the output contract of every skill against good and bad sample outputs, and checks that near-miss prompts route to the right skill. `node scripts/eval-skills.js [skill...]` runs the real skills on a small fixture game with Claude Code, on demand only. See `docs/evals.md`. (#43)

### Changed

- SigmaReview (`sigmareview`) now covers correctness, security (source review plus safe tests on a local instance), and measured performance in one run. It reports every finding with no cap, each written as a self-contained fix brief that an LLM can act on, grouped into waves that can be fixed in parallel. It still never changes code: it publishes one feature-branch pull request with the review file. The report file is now `SIGMAREVIEW-YYYY-MM-DD.md`.
- SigmaBrief (`sigmabrief`) accepts SigmaReview reports and SigmaImprove issues as input and groups briefs into waves, so only independent items run in parallel. Every brief now asks for green baseline checks before changes and ends with a fixed report (`DONE`, `DONE_WITH_CONCERNS`, or `BLOCKED`, plus PR, checks, and open questions). `approval: auto` lets agents record their decisions as rulings instead of waiting. A host's native worktree tool is preferred over manual `git worktree`. A new `session` brief hands the current conversation to a fresh agent.
- The skill picker and `list` now show each skill's short description for people (`short_description` in `agents/openai.yaml`) instead of the agent-facing description cut off mid-word. The picker wraps it onto at most two lines, so narrow terminals show it whole. A skill without that line shows the first sentence of its description. `list --json` still gives the full description. (#39)
- The installer's private files (state, lock, backups, journals, staging) now live in `.agents/.sigmaskills/` (global: `~/.agents/.sigmaskills/`). The folder ignores itself in Git, so `git add -A` no longer stages `.agents/state.json` or backups. Older projects move there on the next write command; `status` and `--dry-run` still read the old layout and write nothing. `--state-dir` and `SIGMA_STATE_DIR` are unchanged. (#34)
- The npm package now ships only the user CLI: about 88 KB smaller unpacked (500,482 B instead of 588,522 B) and 3 fewer files (53 instead of 56). Release and registry automation moved to `scripts/` in the repository, and `sigmaskills release` is gone from the published CLI. Maintainers run `npm run release -- <flags>` from a checkout; the checks it makes are unchanged. (#40)
- Every pull request now rehearses the Release path. A CI job commits the Release identities in a throwaway worktree, then runs the preview, the dispatch checks, and the trusted `validate` and publish steps with a real `npm pack` (`node scripts/release-rehearsal.js`). npm and GitHub lookups, dispatch, and publish are stubbed, so the job needs no secrets. A pull request that breaks packing, such as the `npm pack` JSON bug fixed in 0.2.1, now fails before merge. (#41)
- CI now runs with a read-only token (`permissions: contents: read`) and pins every action to a full commit SHA, like the Release workflows. (#41)
- CI now tests Node.js 22 and 24 on Windows, macOS, and Linux. Node.js 20 reached end of life on 2026-04-30, but `engines` stays at `>=20` for this Release so current users on Node.js 20 can still install; one Linux job on Node.js 20 keeps that promise tested. A later Release may raise it. (#41)
- The README is short again. It keeps the quick start, the skills, one install table, and run examples. Command details moved to [`docs/installer.md`](docs/installer.md); releases, registry automation, tests, and CI moved to [`docs/maintainers.md`](docs/maintainers.md). A test keeps it under 1,500 words, with no paragraph over 80 words. (#42)
- The Agent Host registry follows `vercel-labs/skills` at `7407f38`: Droid and Kilo read project skills from `.agents/skills` (Kilo global: `~/.kilo/skills`), fx and sarvam-code are new hosts, and Antigravity, antigravity-cli, and deepagents leave the universal-prompt list. Existing installs keep their recorded paths.

### Removed

- SigmaPerformance (`sigmaperformance`). Its measurement method and evidence classes are now part of SigmaReview.

### Fixed

- The release tool now treats a breaking change before 1.0.0 as a minor version step, as SemVer allows for 0.y.z versions, instead of jumping to 1.0.0.
- The README no longer points to the v0.2.1 zip as the latest Release.
- The finished 0.3.0 `plan.md` is removed from the repository root; its content lives in issue #3 and PR #29.
- `update` no longer stops when a skill that left the Skill Pack is still installed. The manifest lists retired skills (`sigmaperformance`); `update` leaves them unchanged, lists them under *Retired skills*, and names the `uninstall` command that removes them.
- An unknown skill id now fails with `unknown skill '<id>'` before any planning, for `install`, `update`, `restore`, and `uninstall`. `uninstall --skill nope` said `stale-state` before. (#38)
- A value flag with a missing, empty, or dash-prefixed value now fails with the flag name. Before, `--skill --yes` read `--yes` as a skill id, and a value flag at the end of the command was ignored. One flag table now parses and checks every flag; all current flags and aliases still work. (#38)
- The registry sync test writes into a temporary folder instead of `registry/agent-hosts.json`, so parallel test files no longer read a half-written file and fail at random.
- Update previews show the relevant release notes and correct running-version relation, omit empty sections, and ask for outside-edit choices only when needed. JSON field names and the installed-side relation remain compatible. (#36)
- Lock recovery serializes competing takeovers, preserves fresh incomplete records, and checks unique ownership when releasing. Locks expire after 24 hours; a crash-leftover takeover guard stops safely with recovery instructions. Legacy migration uses the same lock. (#37)
- Untouched copies of earlier Releases are recognized again. `registry/skill-baselines.json` now holds the file hashes of 0.1.0, 0.2.0, 0.2.1, and 0.3.0, rebuilt from their git tags (`node scripts/backfill-baselines.js <tag>...`), and `npm run release -- --write-identities` adds the outgoing Release each time. Such a copy shows as `legacy` with high provenance and upgrades with no `--adopt-*` flag; a changed copy still needs a choice. (#35)
- Install plans now label files from the installer's point of view: *Additions* are files the new Release brings, *Deletions* are files the install removes. They were swapped before. (#35)

## [0.3.0] — 2026-09-08

### Added

- SigmaRefactor (`sigmarefactor`) scans and reconciles the five largest maintained files, reads them fully, discusses behavior-preserving refactoring choices with the user, and verifies approved changes.

### Fixed

- The interactive installer stops repeating unchanged static pages and pauses standard input during cleanup, so confirmed installs return to the shell reliably.
- The installer opens directly to skill selection, keeps destination pages within eight rows, and offers line-based commands in plain terminals. Help preserves cancellation, and short terminals keep focus and controls visible.
- Package tests compare complete trees and bytes for all five skills, including customized reinstall protection and updates.

## [0.2.1] — 2026-08-27 (GitHub Release only)

### Changed

- The Agent Host registry now includes Posit Assistant from the pinned `vercel-labs/skills` revision `dd3ca3c85581`.

### Fixed

- The destination picker paints one compact row per path, windows a live TTY list, groups search hits that share a path, and leaves the alternate screen before cancel or error copy so Windows does not stack or swallow that text.
- Registry Sync no longer fails when a leftover `registry/sync-*` branch still exists: it replaces that generated branch, or reuses a matching open pull request, and still refuses human branches.
- Release packing reads `npm pack --json` after prepack logs, so publication can rebuild the tarball digest.

## [0.2.0] — 2026-08-20

### Added

- Safe Agent Host registry additions and description-only changes may auto-merge after required checks and publish a patch Release through the trusted idempotent publication primitive. Destination, ID, alias, detection, platform, membership, removal, and unknown changes still need owner review. Version calculation serializes concurrent runs against live npm and GitHub state. The generated branch is deleted only after verified merge and matching publication. Automation cannot change skills, CLI behavior, unrelated work, human branches, or major/minor Releases, and it never overwrites an existing npm version.
- Release-candidate qualification packs the published tarball and proves install, adoption, status, update, unsafe resolution, restore, uninstall, uninstall-all, and purge on that artifact. Unknown newer state schemas fail without mutation; supported migrations keep ownership and backup references. The package allowlist, Skill Revisions, and publication preflight agree. Bundled install, status, uninstall, and restore stay offline. CI runs the suite on Windows, macOS, and Linux for Node.js 20+.
- Guarded Agent Host registry automation fetches a pinned upstream revision as data, runs converter code only from an exact trusted default-branch SHA, and opens a tightly scoped pull request limited to `registry/agent-hosts.json`, `registry/source.json`, and the pinned upstream fixture. Semantic classification allows only validated new hosts and description-only changes; path, ID, alias, detection, platform, membership, removal, and unknown changes stay blocked. Generated pull requests record the upstream commit, full semantic diff, validation evidence, and blocked reasons. Forks, human branches, stale heads, moved default branches, failed checks, and concurrent runs cannot be auto-authorized. This automation does not auto-merge, publish npm, close unrelated issues or pull requests, or delete unrelated branches.
- The Sigma Installer `release` command prepares one immutable publication preview from the accepted source commit and, after `--expected-commit`, `--expected-version`, and `--expected-digest`, dispatches the trusted GitHub workflow that rebuilds that commit, verifies the artifact, and publishes matching git tag, GitHub Release, and npm provenance under `latest`. `--yes` is not authority. Missing npm reservation, trusted publisher, protected `release` environment, or a conflicting version/tag/Release fails closed. Partial success is retried without overwriting versions or duplicating Releases. Ordinary merges never publish.
- The Sigma Installer `purge` command removes all Sigma-owned active content, customizations, locks, state, journals, and backups in one explicit Project or Global scope: it prints an exact ownership plan, requires the typed phrase `purge SigmaSkills` (or `--confirm-purge` with that phrase), and does not treat `--yes`, CI, non-TTY, or JSON as authority. Purge never infers ownership from folder names. Unowned occupants stop the command. Durable journaling and reversible quarantine keep the ownership manifest until owned trees are moved; interrupted cleanup leaves recoverable quarantined state.
- The Sigma Installer `uninstall --all` command composes Uninstall Review across every recorded Sigma skill in one explicit Project or Global scope: there is no review-skipping fast path; the aggregate plan lists every skill, owned destination, canonical dependency, state change, and retained backup; keep choices leave shared state intact; changed skills default to backup so snapshots stay restorable; project and global scopes stay isolated; cancellation or failure writes a durable recovery journal and restores the failed skill; human, dry-run, and JSON results report removed, retained, skipped, and failed skills.
- The Sigma Installer `uninstall` command runs Uninstall Review per selected skill: clean skills offer remove or keep; changed, customized, or malformed skills offer backup-and-remove, keep, export, or permanent-delete-current. The preview lists every path, method, scope, and remaining canonical dependency. Execution revalidates leaves, deletes a link itself never its target, keeps canonical content while dependents remain, leaves older backups on permanent delete, and writes state only after filesystem commit. Missing, stale, unowned, divergent, and wrong-target cases stop without partial ownership.
- The Sigma Installer `restore` command returns the latest retained backup for a skill: the preview names Release, Skill Revision, creation date, verified size, scope, canonical target, and affected links or copies; content and metadata are integrity-checked and staged before any live write; a successful restore makes the displaced tree the new one-step backup; identical content is a no-op; missing, truncated, tampered, schema-incompatible, insufficient-space, stale-ownership, occupied-unowned, and failed Windows fallback cases write nothing.
- The Sigma Installer `update` command diagnoses missing, duplicate, reversed, nested, and malformed customization markers, blocks automatic update for that skill, shows exact proposed repair bytes when a unique mechanical repair exists, and requires `--malformed-markers skip|repair|replace`. Repair never infers marker boundaries; skip leaves the skill while others continue; replace backs up then clean-installs. Combined outside drift keeps all content until both resolutions are explicit, and failure paths write nothing partial.
- The Sigma Installer `update` command classifies outside-customization edits, shows local-only and concurrent effects, and lets a user skip, export, or approve a whole-skill replace with an integrity-checked private backup. Skip leaves that skill unchanged; export uses a planned path, refuses collisions, and removes partial output; a prior backup is kept until the new tree and metadata commit, and cleanup failure may retain two backups with recorded debt.
- The Sigma Installer `update` command replaces selected whole skills with the Release bundled in the running CLI: it groups changed and unchanged skills, shows changelog and whole-skill diffs, preserves Skill Customization bytes exactly, updates the canonical copy and its links or matching copies together, and stops without mutation on unknown state schemas, missing bundled revisions, or unsafe drift.
- The Sigma Installer `status` command reports managed Project and Global Installation state and drift without writing files or contacting the network: live hashes and link checks classify clean copies, valid Skill Customization, outside edits, missing or extra resources, malformed markers, missing destinations, stale state, broken or wrong-target links, and copy disagreement.
- The Sigma Installer hardens Emberforge for real terminals: the accepted warm LAPI palette stays, layouts reflow below 76 columns, `?` opens keyboard help, reduced-motion/`NO_COLOR`/CI/JSON/non-TTY modes drop animation, truecolor through ASCII fallbacks keep safety copy, and the cursor restores after success, failure, interrupt, EOF, and exceptions.
- The Sigma Installer protects Global Installation with two confirmations, sandboxed user-home paths, schema-versioned global state, and the same adoption rules as Project Installation: `--global` plus `--yes` are required to write; CI, TTY, JSON, and Agent Host detection never imply that authority.
- The Sigma Installer migrates changed, duplicate, older, pre-marker, and unverified Sigma-looking trees with explicit replace, skip, or export choices: known legacy provenance requires a bundled baseline, a complete private backup is committed before replace, valid customization is preserved, and malformed markers are not guessed.
- The Sigma Installer adopts exact current official copies and valid links in place: valid Sigma state, then exact bundled Skill Revision, then resolved link target. Generic `skills-lock.json` entries never imply Sigma ownership.
- The Sigma Installer recommended link method: Windows directory junctions and macOS/Linux symbolic links to the canonical `.agents/skills` copy, with an explicit copy alternative, informed copy fallback, and ownership records for canonical dependencies.
- The Sigma Installer Project Installation destination picker: every bundled Agent Host stays searchable, only `.agents/skills` is selected by default, host-specific destinations require an explicit choice, and ownership state records each managed copy.
- The first npm package is `@djordje-stojanovic/sigmaskills` because the unscoped name is too close to an existing package. The installed command remains `sigmaskills`.
- The Sigma Installer's interactive Project Installation through plain `npx @djordje-stojanovic/sigmaskills`, with manifest-driven multi-skill selection, exact destination confirmation, cancellation-safe prompts, and no-color, static, and narrow-terminal modes.
- Structural regression tests (`npm test`) and GitHub Actions CI so skill registry, README wiring, templates, and SigmaWrite soft-steer invariants cannot silently drift.
- Root [`AGENTS.md`](AGENTS.md): mandatory work rules and clear-writing rules, project map, and the `KNOWN_SKILLS` + README + CHANGELOG update rule.

### Fixed

- `npm test` lists `test/*.test.js` files in a runner script so Node.js 20 CI runs the suite without glob expansion. Registry pin hashing ignores CRLF from Windows checkout so the fixture still matches `contentSha256`.

## [0.1.0] — 2026-08-11

First public release. Portable [Agent Skills](https://agentskills.io/) for Codex, Pi, Claude Code, Cursor, and compatible hosts.

### Idea

Ship high-rigor, installable agent skills (not apps): full-repo audits, performance investigation, parallel-agent briefing, and clear technical writing voice — each with a tight operating contract and `npx skills add` / Codex `$skill-installer` install paths.

### Skills

- **SigmaReview** (`sigmareview`) — One-shot full-repository engineering audit; single findings Markdown report opened as a report-only PR; no runtime code changes.
- **SigmaPerformance** (`sigmaperformance`) — Calibrated, audit-only performance investigation; measured and mechanically proven bottlenecks; single report PR; no runtime-source edits by default.
- **SigmaBrief** (`sigmabrief`) — Prompt factory: turns issues/work into paste-ready agent briefs; chat-only; does not implement or open product fix PRs.
- **SigmaWrite** (`sigmawrite`) — STE-inspired clear technical English for explanations; soft steers (not hard numbered rules); pasteable system-prompt block; chat style only.

### Repository

- MIT license and root README with multi-host install/run/output contracts (Codex, Claude Code, Cursor, Pi, OpenCode, LAPI-style paths, and Agent Skills–compatible TUIs).
- GitHub Issue Forms + PR template (from github-issue-kit), tailored to Agent Skills / prompts / templates work.
- Packaged GitHub Release **v0.1.0** with source zip of all skills.

### Commits since inception

| Date | Commit | Summary |
|------|--------|---------|
| 2026-07-11 | `1867a70` | Publish SigmaReview skill |
| 2026-07-11 | `ddca5b7` | Publish SigmaReview source files |
| 2026-07-12 | `2343d5b` | Add SigmaPerformance skill |
| 2026-07-29 | `71b2c09` | Add SigmaBrief prompt-factory skill |
| 2026-07-29 | `462d291` | Merge PR #1 (`feat/sigmabrief`) |
| 2026-08-10 | `8dcf2b4` | Add GitHub issue forms and PR template from github-issue-kit |
| 2026-08-10 | `3ef4cd8` | Tailor GitHub issue forms and PR template to SigmaSkills |
| 2026-08-11 | `9631834` | Add SigmaWrite skill for STE-inspired clear technical English |
| 2026-08-11 | `5dab832` | Add CHANGELOG and mark v0.1.0 as the first Sigmaskills release |
| 2026-08-11 | `124a666` | Polish v0.1.0 docs for multi-host install and use |

[Unreleased]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.17.0...HEAD
[0.17.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.16.12...v0.17.0
[0.16.12]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.16.11...v0.16.12
[0.16.11]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.16.10...v0.16.11
[0.16.10]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.16.9...v0.16.10
[0.16.9]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.16.8...v0.16.9
[0.16.8]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.16.7...v0.16.8
[0.16.7]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.16.6...v0.16.7
[0.16.6]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.16.5...v0.16.6
[0.16.5]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.16.4...v0.16.5
[0.16.4]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.16.3...v0.16.4
[0.16.3]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.16.2...v0.16.3
[0.16.2]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.16.1...v0.16.2
[0.16.1]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.16.0...v0.16.1
[0.16.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.15.2...v0.16.0
[0.15.2]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.15.1...v0.15.2
[0.15.1]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.15.0...v0.15.1
[0.15.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.14.0...v0.15.0
[0.14.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.12.0...v0.13.0
[0.12.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.11.0...v0.12.0
[0.11.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.9.2...v0.10.0
[0.9.2]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.9.1...v0.9.2
[0.9.1]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.6.1...v0.7.0
[0.6.1]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.5.1...v0.6.0
[0.5.1]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/Djordje-Stojanovic/Sigmaskills/releases/tag/v0.2.1
[0.2.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/releases/tag/v0.2.0
[0.1.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/releases/tag/v0.1.0
