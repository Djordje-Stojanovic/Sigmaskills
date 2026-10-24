"""SigmaDeepLook --ask: exact answers about the structure of a text file and the layout of a picture (fix round 12). Stdlib only.

- Headings by style: "how many section headings are underlined with a line of hyphens (-)", "how many headings start with '##'". Counted over every
  line of the text file with the same reader that prints the `Heading styles` line (reST: any punctuation character, over-and-under or under only;
  Markdown: `#` marks outside code fences, `=` and `-` underlines).
- Row size of a picture: "how many bytes does one stored pixel row occupy, including padding". BMP rows are padded to a multiple of 4 bytes, PCX scan
  lines hold whole planes of an even length, TGA rows are packed.
Each answer says what it counted. A question that does not name its target returns None, and the caller goes on with the next route.
"""
import re
from pathlib import Path

import dl_textx

PROSE = (".rst", ".rest", ".md", ".markdown", ".txt", ".text", ".mdx")
READ_CAP = 8 << 20
CHAR_WORDS = (("double quote", '"'), ("double-quote", '"'), ("quotation mark", '"'), ("hyphen", "-"), ("dash", "-"), ("minus", "-"), ("equal sign", "="), ("equals sign", "="),
              ("equal character", "="), ("equals character", "="), ("tilde", "~"), ("caret", "^"), ("circumflex", "^"), ("asterisk", "*"), ("plus sign", "+"),
              ("backtick", "`"), ("backquote", "`"), ("colon", ":"), ("underscore", "_"), ("full stop", "."), ("apostrophe", "'"), ("single quote", "'"))
COUNT = re.compile(r"(?i)\bhow many\b|\bnumber of\b|\bcount\b|\btotal\b")   # only a count is answered: "what is the first heading underlined with ..." is not
HEADING = re.compile(r"(?i)\b(?:headings?|section titles?|section headers?|titles?|sections?)\b")
UNDER = re.compile(r"(?i)\bunder-?lin\w*|\bunder-?scor\w* (?:with|by)\b|\bunderlin")
BOTH = re.compile(r"(?i)\b(?:over-? ?and-? ?under(?:line)?\w*|over- ?and ?under\w*|both (?:above|over) and (?:below|under)\w*|above and below|overlin\w*|over and under|over- and under\w*)\b")
STARTS = re.compile(r"(?i)\b(?:start|begin|open|prefix|mark)\w*\b")
HASHES = re.compile(r"(?<![\w#])(#{1,6})(?![\w#])")
PAREN_CHAR = re.compile(r"[(\[]\s*['\"`]?([-=~^*+`:_.'\"#!$%&,;<>?/@\|])['\"`]?\s*[)\]]|['\"`]([-=~^*+`:_.'\"!$%&,;<>?/@\|])['\"`](?![\w])")
KIND_WORD = {"underline": "underlined with", "both": "over- and underlined with", "mark": "marked with"}


def _text(lj):
    p = Path(lj.get("file") or "")
    if p.suffix.lower() not in PROSE or not p.is_file():
        return None
    import dl_core as core
    with open(p, "rb") as fh:
        raw = fh.read(READ_CAP + 1)
    text, _enc = core.decode_text(raw[:READ_CAP])
    return (p, text, len(raw) > READ_CAP) if text is not None else None


def parse_heading(q):
    """-> (kind, character) or None. kind: 'underline', 'both' or 'mark'."""
    if not HEADING.search(q) or not COUNT.search(q):
        return None
    m = HASHES.search(q)
    if m and STARTS.search(q) and not UNDER.search(q):
        return "mark", m.group(1)
    if not UNDER.search(q) and not BOTH.search(q):
        return None
    ch = None
    pm = PAREN_CHAR.search(q)
    if pm:
        ch = pm.group(1) or pm.group(2)
    if not ch:
        for w, c in CHAR_WORDS:
            if re.search(r"(?i)\b" + re.escape(w) + r"(?:e?s)?\b", q):
                ch = c
                break
    if not ch:
        return None
    return ("both" if BOTH.search(q) else "underline"), ch


def heading_answer(q, lj):
    want = parse_heading(q)
    src = _text(lj) if want else None
    if not src:
        return None
    p, text, capped = src
    lines = dl_textx.lines_of(text)
    styles = dl_textx.heading_styles(lines, p.suffix.lower() in (".rst", ".rest") or len(dl_textx.directives(lines)) >= 2)
    kind, ch = want
    n = sum(c for k, cc, c in styles if k == kind and cc == ch)
    verb = KIND_WORD[kind]
    if kind == "mark":
        out = [f"Answer: {n:,} heading{'' if n == 1 else 's'} start{'s' if n == 1 else ''} with exactly '{ch}' (counted over every line of {p.name}, outside code fences; headings with more # characters are counted under their own mark)"]
    else:
        out = [f"Answer: {n:,} heading{' is' if n == 1 else 's are'} {verb} '{ch}' (counted over every line of {p.name}; a heading is a title with that line directly under it"
               + (", or above and below it)" if kind == "both" else ")")]
    out.append(("All heading styles: " + ", ".join(f"'{c}'{' over and under' if k == 'both' else ' underline' if k == 'underline' else ''} x{c2}" for k, c, c2 in styles) + ".")
               if styles else "The text has no heading by these rules.")
    if capped:
        out.append("PARTIAL: only the first 8 MB of the file was read.")
    return out


ROW_WORDS = re.compile(r"(?i)\b(?:stored\s+)?(?:pixel\s+|scan\s?line\s+|image\s+)?(?:rows?|scan\s?lines?|stride)\b")
SIZE_WORDS = re.compile(r"(?i)\b(?:bytes?|stride|occup\w+|padding|padded)\b")


def row_answer(q, lj):
    """How many bytes one stored pixel row (BMP), scan line (PCX) or row (TGA) takes, from the header."""
    if lj.get("type") != "image" or lj.get("subtype") not in ("bmp", "pcx", "tga"):
        return None
    if not (ROW_WORDS.search(q) and SIZE_WORDS.search(q)) or re.search(r"(?i)\bpixel\s*\(?\s*\d+\s*[,;]", q):
        return None
    import dl_legacy as L
    with open(lj["file"], "rb") as fh:
        raw = fh.read(4096)
    st = lj["subtype"]
    info = {"bmp": L.bmp_info, "pcx": L.pcx_info, "tga": L.tga_info}[st](raw)
    if not info:
        return None
    got = L.row_size(st, info)
    if not got:
        return None
    n, how = got
    lines = [f"Answer: {n:,} bytes per stored pixel row ({how})."]
    if st == "bmp":
        lines.append(f"BMP {info['w']:,} x {info['h']:,} px, {info['bpp']} bits per pixel, {'top-down' if info['top_down'] else 'bottom-up'} rows, pixel data at offset {info['offset']}; {info['h']:,} rows x {n:,} bytes = {info['h'] * n:,} bytes of pixel data.")
    elif st == "pcx":
        lines.append(f"PCX {info['w']:,} x {info['h']:,} px, {info['bpp']} bits per pixel, {info['planes']} plane(s), {info['bpl']} bytes per plane of one scan line (header field).")
    else:
        lines.append(f"TGA {info['w']:,} x {info['h']:,} px, {info['bpp']} bits per pixel, {'top-down' if info['top_down'] else 'bottom-up'} rows, pixel data at offset {info['offset']}.")
    return lines


def answer(q, lj):
    import dl_r13   # fix round 13: first or last link definition / anchor / label, the deepest nesting level
    return heading_answer(q, lj) or row_answer(q, lj) or dl_r13.answer(q, lj)
