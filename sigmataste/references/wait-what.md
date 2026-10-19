# The wait-what checks

Three checks for the moment a reader stops and thinks "wait, what is that?". They run beside the lenses, on every pass, and end in one fix list.

They never block. They are not a lint and have no fixed rules: no word counts, no pass marks, no word lists. For each case, judge as a person with taste would: does this reader get lost? Skip a check when its source does not exist (no glossary, no DESIGN.md, a target that is not a UI) and say so in one line.

## 1. Glossary in sync

Find the project's glossary by looking: a glossary file, a context or domain file, a "words we use" section. Then read the words the project really uses: UI labels, docs, comments, names in the code and files you can see, and the target itself.

Name:

- **A missing word.** The project uses it, a newcomer would not know it, and the glossary is silent. Skip everyday words and words any reader of that field knows.
- **A word with two meanings.** Two places use one word for two things, or two words for one thing. Say where, and which meaning the glossary (or the owner's main use) fixes.

## 2. Glossary current

Read each glossary entry against the project as it is now. Name an entry that nothing uses any more, or whose meaning drifted away from how the project uses the word today. Each item gets one suggested action and a reason:

- **update:** the word lives, its meaning moved.
- **merge:** two entries say one thing.
- **retire:** the word is gone from use but old text still names it; keep a short "was" line so old text still reads.
- **delete:** nothing uses it and no old text names it.

Nothing is moved or deleted by the pass. The calling agent or the owner decides.

## 3. DESIGN.md

When the repo has a DESIGN.md (the one design file: colours, fonts, layout, components) and the target is a UI, compare the screenshots or the markup with it. Name each clash: the anchor, what the file says, what the target shows, and which side looks wrong. The design file may be the older side: say so when the target is clearly the better, newer choice. A target that follows the file but looks poor is a lens finding, not a clash.

## The fix list

Write the result as the plan's "Wait-what fixes" section: one line per item.

`<check> · <anchor> · <what is wrong> → <what to do> · <why>`

The calling agent applies what is true, using judgment, and may drop an item with a reason. An empty check gets one line ("nothing found" or "no glossary").
