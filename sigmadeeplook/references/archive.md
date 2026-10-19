# Archives

zip, tar and its compressed forms, gz, bz2, xz, zst, 7z, rar, iso, cab, jar and apk, and Docker image tars. Rule one: list before you touch anything. Never extract an unknown archive to find out what it holds.

## When look.py is not enough

- A refused archive (exit 2): the look will not extract it, and neither should you. The reason is in Flags. If the human insists, the safe route is a throwaway VM or container, not this machine.
- 7z, rar, iso and cab without 7-Zip: the listing is a Not-looked-at row with an install line.
- Encrypted members are listed, never extracted. A password is the human's to give, and this skill does not guess.
- What an installer inside an archive does: this skill reads it as bytes, never runs it. See binary.md.

## Pipeline

1. Listing with the standard library (`zipfile`, `tarfile`), else bsdtar, else `7z l -slt`: name, size, packed size, ratio, type, flags (`listing.csv`).
2. Screen, on the listing only (`screen.json`). Three kinds of finding. The look refuses the whole archive (exit 2) and reads and extracts nothing when it sees: an absolute path, a drive letter or `..`; a link whose target leaves the archive (absolute, or `..` past the root); two members sharing one byte range (an overlap bomb); an archive inside an archive more than 2 levels deep. It refuses `--extract` only (the members are still read in memory under their own byte caps) for more than 10,000 members, and for more than 2 GiB uncompressed or more than half the free disk. It leaves out only the member it names, from member looks and extraction, for: a ratio above 200 to 1; a duplicate name (every copy); a Windows reserved name (CON, NUL, COM1, a trailing dot or space) or `:`; a device; a link whose target the listing does not show. A relative link that stays inside the archive is harmless: it is listed (type `symlink`) and never followed. A compressed tar is listed until the time cap (90 s, `SIGMADEEPLOOK_TARLIST_CAP`), then the look says PARTIAL.
3. `--extract`, only when the screen passed: one member at a time into the work folder, each path resolved with `realpath` and `commonpath` under the destination, byte and time counters that stop mid-stream, `tarfile` with `filter='data'`. Nothing is written without `--extract`.
4. `--recurse N` looks at the first N extracted members by their own type.
5. Docker image tar: `layers.csv`, the manifest, and whiteout files (`.wh.<name>` deletes a lower-layer file; an opaque whiteout removes a directory's children). Layers are not extracted in order.

## Failure modes

- Zip Slip: `../../evil.sh` written outside the target by code that joins paths without a check. `zipfile.Path` does not sanitise at all.
- Ratio bombs: DEFLATE cannot pass about 1032 to 1 on one member, so a higher ratio is a lie or a stacked layer; nested zips multiply by 1032 per layer; an overlap bomb needs no nesting, so a depth limit alone does not stop it.
- Parsers disagree about overlaps: an archive can pass one tool and blow up another.
- The tarfile `data` filter is the safe default but "does not block all dangerous archive features". The screen stays.
- Windows replaces `: < > | " ? *` in names; a name can change on extraction.
- 7-Zip opens some zips with bad headers that others reject, and the reverse.
- A tar with a huge member can use a lot of memory; the look reads members in streams.

## Show the human

Entry count, total uncompressed size, largest ratio, nested archives, every flagged name (absolute, `..`, links, duplicates), and a decision line: "extract", "skip" or "extract in a VM", with the reason. For Docker images: the layer list with size per layer and the whiteouts. Ask: whether extraction is wanted at all, and into which folder.

## Install (Win/Linux/macOS)

zip and tar need nothing.

- 7-Zip (7z, rar, iso, cab): `winget install 7zip.7zip` / `sudo apt install 7zip` / `brew install sevenzip`.
