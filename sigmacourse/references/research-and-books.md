# Research and books

## Which skill
- SigmaResearch: counted, scored public sources (a floor per teacher or topic, set in the grill). Use for teachers, corpora and practice in the field.
- Matt Pocock `research` (option): one question against high-trust primary sources, written to a file. Use for facts, laws, prices, official numbers.
- SigmaDeepLook: video and audio transcripts, scans, odd file formats. Use for talks, lectures and scanned books.
- SigmaFinanceMan or another field skill when the subject needs models from filings or data.

## Order
1. Pedagogy first: the doctrine evidence and the exemplar courses (`repo-setup.md`, doctrine). It shapes every lesson.
2. The base rate for the goal. It goes on page one.
3. Teachers just ahead of the lesson that needs them, about two at a time. Each teacher file: method, decisions with dates, quotes word for word with sources, mistakes and passes (keep a floor of mistakes, so the course is not a highlight reel).
4. Corpora the grill named, harvested in full, then sorted.
5. World and sub-field primers before their block.

## Source rules
- Every fetched source is kept as a snapshot with a header: URL, published date, accessed date.
- Every quote, date and outcome in a lesson or case file matches a stored file; the schema check fails when it does not.
- Outcomes are computed by a committed script from a dated data file.
- Never send the user's email or name in a request header; use a generic user agent.
- Beliefs from the grill that sound like facts go to a "beliefs to verify" list until a source confirms them.

## The book path
1. **Book list** (after the end-to-end design): one list, `docs/books/book-list.md`: title, author, edition, why, which module, tier. The user buys the books and drops the files in `books/` (git-ignored; narrow the ignore rule to `/books/` so `docs/books/` stays tracked).
2. **Manifest:** match every file to the list (format, text or scan). Scans get OCR first (`sigmadeeplook`). Missing or extra files go to the blockers list.
3. **One distill job per book:** `research/books/<slug>.md`, chapter by chapter. Keep every framework, rule, claim, number and story with a locator (chapter and page, or section). Quotes word for word but short. No cutting at this step. End with a "use in the course" list: which block and topic each part fits, and where the book disagrees with a teacher.
4. **Rolling map** (after every ~5 books): `research/books/map.md`. Book part to block, lesson and teacher; keep or cut with a reason; conflicts stated both ways.
5. **Use:** every lesson job reads the map and cites the notes it uses.

Done when every book has a reviewed note or a logged reason, and the map covers every note.
