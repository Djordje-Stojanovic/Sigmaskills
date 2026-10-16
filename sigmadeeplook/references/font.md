# Fonts

TrueType, OpenType, TTC, WOFF and WOFF2. Validity and quality are not looks: no tool here judges whether a design or its spacing is good. A person looks at the specimen.

## When look.py is not enough

- Design quality, spacing, kerning feel: show the human the specimen and the glyph grid. Do not rate them.
- Shaping of complex scripts (Arabic, Devanagari): needs HarfBuzz. The specimen uses Pillow's layout engine and does not shape complex scripts.
- Hinted rendering at small sizes: needs FreeType output; not produced here.
- A validity gate (OTS) or a quality report (Font Bakery) is for a font going into CI or a website. The look does not run them.

## Pipeline

1. Table directory and the `name` table with the standard library, so a font is identified without any package: family, style, version, designer, licence text (`font.json`).
2. With fontTools: glyph count, `cmap` coverage by Unicode block, characters of basic Latin the font lacks (`MISSING-LATIN`), `fvar` axes of a variable font, `OS/2` weight and width, whether it is TrueType (glyf) or CFF.
3. WOFF2 needs brotli to decompress; without it the table directory and a Not-looked-at row remain.
4. Specimen (`specimen.png`): sample text at three sizes plus a grid of the first 144 mapped characters. The font is re-saved to a temporary copy so Pillow can open a WOFF or WOFF2.
5. OTS and Font Bakery are not run. They appear as a Not-looked-at row with the install line; run them yourself when the human wants a validity gate.

## Failure modes

- WOFF2 and better WOFF compression need extra packages (brotli, zopfli). Without them tools fail or fall back.
- Glyph names: invented names look like `glyph00142`; duplicates get `#n` in ttx. Do not infer meaning from them.
- A glyph's bounding box is not its advance width.
- Pillow length measurements are not additive across kerning; `getlength` ignores line breaks.
- On Windows FreeType keeps font files open; many fonts in one process can hit a file limit.
- A font can carry a licence string that forbids the planned use. Quote it; do not interpret it.
- OTS rejects what it cannot sanitise; a pass means the file parses, not that it is good.

## Show the human

File hash, family and style, glyph count, static or variable (with axes), missing tables, the specimen at two or three sizes with the settings written under it, the list of characters the font lacks if the target text is known, and any file the tools could not read. Ask: which scripts the font must cover, and whether the licence text allows the planned use.

## Install (Win/Linux/macOS)

- fontTools: `pip install fonttools`. WOFF2: `pip install brotli`. Specimens: `pip install pillow`.
- Optional gates, not run by the look: `pip install fontbakery`; OTS from github.com/khaledhosny/ots.
