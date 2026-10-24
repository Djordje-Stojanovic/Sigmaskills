# Logs, subtitles, certificates, model files, disk images, git bundles, EPUB, Avro, EVTX, PSD

One reference for the families that are not big enough for their own page. Same five parts: when `look.py` is not enough, pipeline, failure modes, what to show the human, install lines (all in [installs](installs.md)).

## When look.py is not enough

- Logs and subtitles: it finds the structure and the oddities; whether an error matters, or a subtitle is right, is for a person who knows the system or watched the video.
- Certificates and keys: it reads public fields only. It does not verify a chain, check revocation or open a password-protected container.
- Model files: it never loads them. Quality, licence and behaviour of a model are out of scope.
- Disk and VM images: listed from the header only. It never mounts them; contents need 7-Zip or the hypervisor.

Plain text without a format of its own (notes, catalogues, reST, configs) still gets its structure in step 1: headings of any underline style (a `Heading styles` line counts them per underline character; `--ask "how many headings are underlined with hyphens"` answers), paragraphs (blank-line blocks), which first words open lines (`msgid 121`, `msgstr 121`), `.. name::` directives, the most frequent words, and the last six lines with their numbers. A head view of a long file says `PARTIAL: the first 200 of N lines`; never read it as the whole file.

## Pipeline and traps

| Family | What step 1 gives | Traps it flags | Drill / waits for |
|---|---|---|---|
| **Log** (any text with timestamps, `.log`) | span, line count, volume per minute as a sparkline, levels, top message templates (Drain), the first ERROR and the lines before it | `GAP` (silence in the timeline), `BURST`, `TIME-BACKWARDS`, `ROTATED-MID-TRACE`, `PARTIAL`, `NO-TIMEZONE`, `ROOT-CAUSE-EARLIER?` (a warning shortly before the first error) | `--grep` over `templates.csv`, `errors.md`, `rare.md`, `timeline.csv` |
| **Subtitles** (srt, vtt, sbv, ass, lrc) | cue count, span, reading speed, text file, cue table; each distinct line with its cue count when the text repeats | `OVERLAPPING-CUES`, `FAST-CUES` (above 21 characters per second), `MOJIBAKE` | `--grep` over `text.md`, `cues.csv` |
| **EVTX** | record count, time span from the chunk headers, version | `DIRTY-LOG` (not closed cleanly) | python-evtx adds event ids, providers, levels, messages |
| **Certificates and keys** (pem, der, crt, p12, ssh public key) | subject, issuer, validity, key type and size, names, chain order | `EXPIRED`, `SELF-SIGNED`, `WEAK-SIGNATURE` (SHA-1, MD5), `PRIVATE-KEY` (never printed, even in part) | cryptography (or openssl) for the fields |
| **ML model files** (gguf, safetensors, onnx, pickle, pt/pth/ckpt, hdf5) | architecture, parameter count, quantisation, context length, tensor groups, operators | `PICKLE-EXEC` (the pickle imports `os.system`, `eval`... and would run on load), `PICKLE-UNKNOWN-IMPORT`, `QUANT-MISMATCH` (name says Q8, header says Q4), `TRUNCATED`, `EXTERNAL-WEIGHTS` | h5py for HDF5 layers |
| **Disk and VM images** (qcow2, vmdk, vhd, vhdx, img) | virtual size against stored size, partition table, backing file | `BACKING-FILE` (incomplete without its parent), `ENCRYPTED`, `NOT-MOUNTED` | 7-Zip lists the files inside |
| **Git bundle** | refs, prerequisites, then (with git) commit count, authors, date range, most changed paths from a bare clone with no checkout and no hooks | `INCOMPLETE-BUNDLE` (needs commits you do not have) | git |
| **EPUB** | title, author, language, chapters with word counts, whole text | `DRM`, `FIXED-LAYOUT` | `--page A-B` is not for epub; use `--grep` over `text.md`, `--member` for one part |
| **Avro** | record count, blocks, codec, schema fields | `TRUNCATED` | fastavro adds sample records |
| **PSD** | size, colour mode, depth | `HIDDEN-LAYER` | psd-tools adds layers, text layers, smart objects |
| **Calendar** (ics) | events, time zone of each, recurrences in words with the next occurrences | `UNBOUNDED-RECURRENCE`, `FLOATING-TIME` (no zone) | icalendar + recurring-ical-events for BYSETPOS, RDATE and DST transitions |

## Failure modes

- A log without recognisable timestamps gets line counts and an excerpt, plus a Not-looked-at row for the timeline.
- A pickle is scanned with `pickletools.genops`. A clean scan is not a safety certificate: classes outside torch, numpy and collections are listed as `PICKLE-UNKNOWN-IMPORT`. Prefer safetensors.
- Certificate dates are in UTC. "Expired" is judged against today's date on this machine.
- A git bundle that needs prerequisites is not cloned; the flag names the count.

## What to show the human

The flags that matter, the first error with its context lines, the span and gaps of a log, the signer and validity of a certificate, the pickle imports, and every Not-looked-at row with its install line. Never show a private key, a keystore password prompt or a token.
