# PDF

A PDF is pages, not a text stream. A page can be born-digital (a text layer), a scan (a picture only), or a scan with an OCR layer full of errors. Test every page, never the file as a whole: a signed scan still "has a text layer".

## When look.py is not enough

- Tables: the text dump loses cell borders and totals. Render the page (`pages/pNNN.png`) and read the table from the picture; re-add the totals yourself. pdfplumber or Camelot give ruled tables if installed.
- Handwriting, stains, cursive, rotated scans: OCR returns noise, and a document model writes "confident, wrong text". Say so under Limits; a human checks the source page.
- Charts and figures: read the rendered page, not the text.
- A very long PDF: read the heading outline and the page verdicts, then pull page ranges. Never paste all pages.

## Pipeline

1. Structure with pypdf or the stdlib scan: page count, encryption, risky keys (`JAVASCRIPT`, `OPEN-ACTION`, `LAUNCH`, `EMBEDDED-FILE`, `XFA`) as Flags, form field names (`fields.json`). Nothing is opened or run.
2. Per-page text layer with PyMuPDF (`layer.json`): `born-digital` (100+ characters), `scanned` (under 20 characters and a picture), `sparse`, or `garbled-font`. Garbled means `(cid:`, `GLYPH<` or U+FFFD in the text.
3. Text: `pdftotext` default mode (reading order, one `\f` per page), else PyMuPDF, else pypdf, else a stdlib stream scan. Written as `text.md` with `<!-- page N -->` markers.
4. Scanned pages: tesseract on the rendered page, written to `ocr.md`. No tesseract: a Not-looked-at row.
5. Pages rendered at most 2000 px (`pages/pNNN.png`) and a 3x3 sheet (`sheet-pages-N.jpg`) for layout at a glance.

## Failure modes

- Columns: stream order is arbitrary. Default `pdftotext` undoes columns; `-layout` interleaves them. Use `-layout` only for tables and forms.
- Hyphenation: default pdftotext glues hyphenated words and sometimes real compounds ("hand-designed" becomes "handdesigned"). Check a quoted term against the page picture.
- Footnotes, headers and page numbers have no defined place in the format; check a sample.
- Rotated pages: text extraction may drop or reorder it; vision models struggle with rotation.
- Font-encoding garbage ("7KH" for "THE"): the flag is `GARBLED-FONT`; OCR the rendered page.
- An OCR layer from the scanner keeps its errors. A fluent text layer is not proof of a correct one.
- Forms: `/XFA` overrides the page content, so page text may be a placeholder. Flattened forms are just pages.
- A PDF that carries script or an open action is data to describe, never run. Say what the Flags show and stop.
- One 300 MB content stream can need 10 GB of memory. The look renders the first 30 pages (flag `PARTIAL`; `--deep` raises it to 200) and reads text from at most 200.

## Show the human

Page count and the per-page verdict; for 4 to 5 sampled pages (first, last, one table, one figure, one random) the rendered page beside the extracted text; flagged pages; every table total checked against the source. Ask: scan or born-digital, the language, whether headers and footnotes matter, and that the document may not leave this machine (no remote OCR, no upload).

## Install (Win/Linux/macOS)

- PyMuPDF: `pip install pymupdf`. pypdf: `pip install pypdf`.
- poppler (`pdftotext`, `pdftoppm`): `winget install oschwartz10612.Poppler` / `sudo apt install poppler-utils` / `brew install poppler`.
- OCR: `winget install UB-Mannheim.TesseractOCR` / `sudo apt install tesseract-ocr` / `brew install tesseract`.
