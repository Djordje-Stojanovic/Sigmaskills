# Binaries and executables

PE (`.exe`, `.dll`), ELF, Mach-O, WebAssembly, Java `.class`, Android `.dex`. The skill reads the file as bytes. It never runs it, never loads it, never sends it or its strings anywhere.

## When look.py is not enough

- What the program does: stdlib facts describe a file; they do not explain intent. Disassembly and decompilation need Ghidra, IDA, radare2 or Rizin, and a human who can read the result. The look runs none of them: it names them in a Not-looked-at row. `--deep` adds capa when it is installed.
- Malware verdicts: this look produces leads (entropy, strings, imports, packer hints), not a verdict. Do not tell the user a file is safe or malicious on this evidence.
- Packed files: when `PACKED?` or `HIGH-ENTROPY` is flagged, strings and imports are poor evidence. Say so.
- AI decompilers were trained on Linux x86-64 ELF from GCC. A Windows PE is outside that, so treat them as a second reader only.

## Pipeline

1. Identity: sha256, size, magic, extension. When the kind was found by the file's first bytes, the identity line shows them in hex, in file order (`magic 950412de 00000000`: the first four bytes, then the next four). An extension that disagrees with the bytes (`fake.pdf` that is a PE) is the first Flag.
2. Header, stdlib: PE machine, timestamp, subsystem, sections with size and entropy, imports (all with pefile, DLL names without); ELF class, architecture, sections; Mach-O CPU type; wasm and class versions (`header.json`).
3. Strings: ASCII and UTF-16LE, minimum length 8, capped at 20,000 (`strings.txt`). Keys and tokens are named by kind in Flags (`SECRET?`), never echoed into LOOK.md.
4. Entropy for the whole file and per section. Over about 7.2 in a code section gives `PACKED?`.
5. When installed: `diec` (packer and compiler, `die.txt`). With `--deep` and capa installed: `capa -j` (`capa.json`).
6. Always a hex dump of the first 512 bytes (`hexdump.txt`).

## Failure modes

- Heuristic overreach: a packer or language verdict from a detector is a lead. Read the evidence line, not just the name.
- Section names lie. `.text` can hold data and a packed file can look ordinary until entropy is checked.
- Strings include library noise and decoys; absence of a string proves nothing.
- A compiler timestamp can be zeroed or faked; do not date a build from it.
- Licence gates: IDA, Hopper, JEB and Binary Ninja are paid; this skill names them and calls none of them.
- Tools that drive a disassembler over MCP run with the user's rights and can expose run commands. Not used here.
- Uploading a sample to a scanning service leaks it. The skill has no upload code; asking the human first is the only route.

## Show the human

Hash, size, type, architecture, section table with entropy, the imports that matter, the strings that identify the program, detector verdicts with their evidence lines kept apart from facts. What was not run: execution, decompilation, network. Ask: where the file came from, whether a deeper pass with a disassembler is wanted, and that the sample may not be uploaded unless the human says yes.

## Install (Win/Linux/macOS)

Nothing is required for the header, strings and entropy.

- pefile (imports and resources): `pip install pefile`.
- Detect It Easy (`diec`): download from github.com/horsicq/DIE-engine (Windows); `brew install --cask die` (macOS).
- capa: `pip install flare-capa`.
