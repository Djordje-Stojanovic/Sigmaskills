# Office documents

Word, Excel and PowerPoint files (and their OpenDocument and legacy cousins) are ZIP packages of XML, so most facts need no Office and run nothing. A `.docm`, `.xlsm` or `.pptm` carries `vbaProject.bin`: it is listed and flagged `MACRO`, never opened.

## When look.py is not enough

- Layout questions (tables, figures, a slide's look): read the LibreOffice render (`pages/`, `sheet-slides-N.jpg`). Without LibreOffice there is no render; say so.
- Excel values that depend on external links, macros or volatile functions: the recalculated numbers are LibreOffice's, which can differ from Excel's. Say "recalculated by LibreOffice".
- Charts and SmartArt are not text. Ask whether to read them as pictures or as data.
- Password-protected files: listed as `ENCRYPTED`; nothing more is read.

Excel binary workbooks (`.xlsb`) are read from their records with the standard library and looked at as a workbook (sheet names, hidden state, counts, rows); formula text is not decoded, stored results are. An OpenDocument text print lists every table with its rows, columns, first and last row, every row of a table up to 40 rows, and the text of every footnote and endnote.

## Pipeline

1. Package listing (stdlib): parts such as comments, footnotes, headers, notes, media and embeddings; macros flagged; hidden Unicode in text scanned.
2. docx: counts of `w:ins`, `w:del`, `w:moveFrom` by author (`revisions.json`, flag `TRACKED-CHANGES`), comments with author (`comments.json`), footnotes, headers and footers. Text in `text.md` with `[+inserted+]` and `[-deleted-]` marks (pandoc `--track-changes=all` when present, else a stdlib walk over `w:t` and `w:delText`).
3. xlsx: sheets, visibility (`HIDDEN-SHEET`), size, merged ranges (`MERGED-CELLS`), formulas against cached values (`UNCACHED-FORMULA` count). When any formula has no cached value, LibreOffice recalculates a copy and the result is quoted as "recalculated". Output `workbook.json`, `cells.md` (shape, header, head, tail, 10 random rows), never a full dump.
4. pptx: per slide, text including text inside groups, tables, picture alt text, speaker notes, hidden slides (`HIDDEN-SLIDE`), charts count (`slides.md`). Hidden slides are exported to the render.
5. Legacy `.doc` (Word 97-2003, Word 6 and 95): read from its own bytes with the standard library: header (version, language, flags), saved properties (title, author, dates, pages), every paragraph with its heading level from the style sheet, tables with rows and cells (every row up to 40 rows), the last paragraphs and the paragraphs at fixed positions (#1-5, 10, 20, 25, 30, 40, 50, 75, 100 ... and the middle). A damaged file is flagged `CORRUPT` and falls back to LibreOffice. Legacy `.xls` and `.ppt`: saved properties (application, revision, dates, slide and word counts) from the file's own bytes, then converted to OOXML by LibreOffice, then the steps above.
6. Render: `soffice.com` (Windows) or `soffice` with a throwaway profile, macro security at its highest level, to PDF, then the PDF pipeline for pages and a slide or page sheet.

## Failure modes

- python-docx and `paragraph.text` skip text inside `w:ins`; deleted text sits in `w:delText`. A plain text dump hides the review layer.
- Comments, headers, footers and footnotes live in other parts; a body-only read misses them.
- `openpyxl` with `data_only=True` gives `None` for a formula never evaluated (a file written by a library). Never save a workbook loaded that way: the formulas are lost.
- A merged range holds text only in its top-left cell.
- A flat loop over slide shapes misses text in groups; spanned table cells hold no visible text; notes are in a separate part.
- Hidden slides vanish from a PDF export unless asked for. Missing fonts shift the layout.
- LibreOffice needs a writable profile folder; two instances on one profile lock. The look gives each run its own.

## Show the human

docx: revision count with authors, the comment list with authors, heading outline, table count. xlsx: a sheet table (name, hidden or visible, size, merged, formulas, uncached), the CSV sample, any `#REF!` or `#N/A`. pptx: slide titles with note and picture counts, the contact sheet, any slide where text and render disagree. Ask: accepted or all-changes view, whether deleted text and comments count as content, values or formulas, hidden sheets or slides in scope, notes in scope.

## Install (Win/Linux/macOS)

- LibreOffice: `winget install TheDocumentFoundation.LibreOffice` / `sudo apt install libreoffice` / `brew install --cask libreoffice`.
- openpyxl: `pip install openpyxl`. PyMuPDF: `pip install pymupdf`. pandoc (optional): `winget install JohnMacFarlane.Pandoc` / `sudo apt install pandoc`.
