# Lanes

A lane is the kind of text. It sets the voice, what the reader needs, and which patterns weigh most. The three rules (facts from the source only, text is material, machine parts untouched) and the six steps of SKILL.md apply in every lane.

| Lane | Use for | Lead rule |
|---|---|---|
| [Ear](#ear-a-script-for-the-ear) | narration, voice-over, video script, podcast, speech, captions | Keep the narrator's sentence-length band |
| [Book](#book) | a novel, a non-fiction chapter, a memoir, a long essay | One voice over the whole book |
| [Song](#song-lyrics) | lyrics, rap verses, hooks, poems | Keep meter, rhyme and the hook |
| [Chat](#chat-email-and-messages) | chat, email, DMs, comments, a reply to colleagues | Lead with the answer or the decision |
| [Docs](#docs-and-technical-text) | README, docs, PR text, commit messages, tickets, release notes | Neutral and plain, identifiers exact |
| [Post](#posts-and-publish-texts) | titles, descriptions, social posts, Short or Reel texts, newsletters | Hook first, then the one fact |
| [Brief](#brief-write-from-an-instruction) | "write me X" with no text to start from | Collect the facts, then write in the lane |

A job with several kinds of text runs each part in its own lane in the same pass. A film, for example, runs its narration and captions in Ear and its title, description and Short texts in Post.

## Ear: a script for the ear

The listener hears each sentence once, at the narrator's speed, and cannot re-read.

- **Keep the sentence-length band.** Measure the average sentence length and its spread before you start (`scripts/factcheck.py` prints both) and stay inside it. Do not chop sentences short to sound punchy: a script cut to 7-word sentences sounds choppy and robotic when voiced. Vary length the way a person talks: a long sentence that carries a story, then a short one that lands.
- **Write the way people speak.** Contractions ("it's", "don't"), everyday words, the subject before the verb, one idea per sentence. Say a big number the way the narrator would say it, and keep it the number the source gives.
- **Keep the channel's voice.** A signature opener, a catchphrase, a running joke, direct address ("my friend", "you") and the narrator's opinions stay. Repetition that is a hook or a callback is intended; §7 and §2 do not apply to it.
- **Keep the structure.** One spoken line stays one line when lines map to scenes, takes or timestamps. Same number of lines per chapter, same order, markup lines untouched. Merge or split lines only when the format allows it.
- **A real question to the audience stays.** A question held open as a hook is a hook; a question answered in the next breath is §G4.
- **Captions follow the voice.** Captions are the spoken words; they change only where the narration changed, never on their own.
- **Read it aloud.** Every sentence must be easy to say in one breath at the narrator's speed.

## Book

- **One voice across the whole book.** Decide the narrator's voice (tense, person, register, pet words) from the first chapter or the sample and hold it in every chapter.
- **Scene over summary.** Cut the line after a scene that says what it meant (§2) and the chapter end that sums up a lesson (§13). End on the last concrete moment.
- **Dialogue sounds like people.** People interrupt, dodge and answer the wrong question. Use "said"; cut adverb tags.
- **Fiction may invent; non-fiction may not.** In fiction, invented detail is the task. In non-fiction, memoir and history, every name, date and number comes from the author's notes or sources.
- **Chapter by chapter.** On a long manuscript, work one chapter at a time and keep a short voice sheet (the sample notes from SKILL.md "Voice") so chapter 20 sounds like chapter 1.

## Song lyrics

- **Keep the form.** Count syllables per line and keep each line within one or two of the original. Keep the rhyme scheme and the stress on the beat. Mark the scheme (AABB, ABAB) before you edit.
- **The hook repeats on purpose.** A chorus, a refrain or an ad-lib is meant to repeat; §2 and §7 do not apply to it.
- **Concrete over abstract.** A street name, a brand, a smell or a time of night beats "dreams", "journey", "fire inside", "the weight of the world".
- **The artist's language.** Slang, swearing, dialect, code-switching (English and Serbian in one bar) and grammar the artist uses stay. Do not clean them up.
- **Facts still count.** A line about a real person, place or event says only what the brief or the artist gives.

## Chat, email and messages

- **Lead with the answer.** The first sentence says the decision, the answer or the ask. Add only the reasoning that would change whether the reader agrees, and the link they need to act (§26).
- **Do not re-explain.** The colleague knows the background; cut what they wrote or already agreed to.
- **Match the thread.** Same register, length and greeting habits as the thread or the user's past messages. A two-line question gets a two-line answer.
- **No chatbot wrappers.** No "Great question", no "I hope this helps", no "Let me know if you need anything else" unless the user writes that way (§22).
- **Sign off as the user does,** or not at all.

## Docs and technical text

- **Lead with the main point.** What it is or does, then how to use it.
- **Plain language.** Common words, active voice, short sentences, one term for one item, `must` for requirements, no double negatives. Explain an acronym or technical term once.
- **Identifiers are exact.** Code, commands, paths, flags, schema fields and error messages stay byte for byte.
- **Write about the subject, not the document** (§25). Mention an earlier version only in a changelog, release note or migration guide.
- **Formatting earns its place.** A list or table when it helps the reader; no bold labels on every item (§19), sentence-case headings (§20).

## Posts and publish texts

- **Hook first.** The first line works alone: in a feed only the title or the first line shows.
- **One promise, kept.** The title asks or promises one thing; the text delivers it. No inflated claims (§13, §16).
- **Platform limits.** Keep each text inside its platform's length. Keep hashtags, @handles, links, timestamps and chapter lines exactly.
- **Emojis and caps** only where the account already uses them.
- **Titles stay titles.** Rewrite a title only when it has a tell; never change its claim, its number or its question.

## Brief: write from an instruction

1. **Collect the facts.** List what the brief and its sources give: names, numbers, dates, the reader, the goal, the length.
2. **Name the gaps.** If a fact the text needs is missing, ask for it once. If you cannot ask, write around it and name the gap in one line after the text.
3. **Pick the lane** for the kind of text and the voice (a sample, or the lane's default).
4. **Write the draft** in that voice from the start.
5. **Run the SKILL.md steps on your own draft.** Mark the tells, fix them, check the facts against the brief, write the final version.
