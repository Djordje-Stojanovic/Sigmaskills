---
name: easytalk
description: Plain, short English with interactive status and question boards. Use when the user says "easy talk", asks for an EasyTalk board, or pastes an EASYTALK REPLY. Keep the mode on until "easy talk off". Do not use for building a product dashboard or for prose editing alone (SigmaWrite).
---

# EasyTalk

Use short, clear chat and one interactive board for status reports or batches of questions. The board lets the user read, choose, comment, and copy answers back to the agent.

**On:** "easy talk" or an explicit invocation. **Off:** "easy talk off". Keep the mode on for this conversation until the user turns it off. A pasted `EASYTALK REPLY` activates reply handling.

## Chat and replies

Write plain English: short sentences, active voice, common words. Explain unfamiliar technical terms briefly. Lead with what changed for the user or what they need to do. With a board, send its link and one to three useful lines. Without one, keep the reply to eight lines where the task allows. Use numbers when they explain progress.

Answer every user question explicitly, one by one. Quote each question briefly, then give its answer. If an answer is open, say why and what will resolve it.

When the user pastes an `EASYTALK REPLY`, process every answer and comment by id, including `General`. A read tick means seen; it is not approval. A status or option expresses the user's choice. Apply it within the user's authorized task. Carry every `Not read` card to the next board with the same id and content. Keep the board data available in the conversation or saved board so these ids can be resolved. If an id has no available source, state that gap rather than invent its content.

## When to make a board

Make one board for a status report, the end of a substantial piece of work, three or more questions, or three or more prompts or actions. Keep a single yes/no question in chat. Each board has three groups in this order; empty groups disappear:

| Array | Shown as | Holds |
|---|---|---|
| `DO` | Your action | Questions first, then prompts and manual tasks |
| `ANS` | Answers to your questions | One card per user question |
| `FYI` | FYI | Changes and useful information that need no action |

## Build and deliver

Resolve [template.html](template.html) relative to this installed skill's directory, not the project root. Copy it to a writable scratch or output directory using the machine's native shell or file tool. Give the copy a descriptive name such as `status-board.html`. Keep the installed template untouched.

Read the copy's `DATA` block near the top and replace only `PAGE`, `DO`, `ANS`, and `FYI`. Preserve its style and script. Use generic project facts for the current task, not the sample content. Give each board a unique title; browser drafts are stored by title. Use a new title when reusing ids for different content. An update of the same board keeps its title and ids so the draft survives.

If the host has an HTML Artifact or preview tool, follow that tool's required contract and publish or open the copy. For updates, reuse the same path when the tool supports it. If no such tool is available, provide a link to the saved HTML file and tell the user to open it in a browser. It needs no server, package, external asset, or lab-specific tool. If HTML cannot be delivered, put the same ids, groups, options, and prompts in chat and accept a plain-text reply; state that interactive controls are unavailable.

### Board data

| Field | Use |
|---|---|
| `PAGE.title`, `PAGE.sub` | Board title and short instructions |
| `PAGE.suffix` | Optional text appended to each copied prompt; default empty |
| `id` | Unique short id: Q for questions, D for tasks, A for answers, F for FYI. Unread carryovers keep their id |
| `t` | One line with the outcome or question; trusted HTML allowed |
| `q` | ANS only: short quote of the user's question |
| `b` | Optional trusted HTML body, up to four bullets |
| `tag`, `tc` | Optional chip; class `ok`, `warn`, or `acc` |
| `p` | Prompt with copy button and done / doing / not now choices |
| `act: 1` | Manual task with the same status choices, without a prompt |
| `o`, `rec` | Question options and recommended index. Put the recommendation first, at index 0; it shows ★ |

Each card has a read tick and free text. Typing or picking marks it read. With hide read enabled, the card stays visible while it has focus so the user can finish editing. The General answers box holds comments about the whole board. Drafts stay in this browser; copying produces text to paste back and does not send it.

Generate valid JavaScript strings when replacing DATA: escape quotes, backslashes, line breaks, and `<` as `\u003c` so pasted text cannot end a script block. HTML fields are for agent-authored markup; HTML-escape untrusted text embedded in `t`, `b`, or `tag`. Keep ids simple letters and digits, and `tc` within the listed classes.

### Keyboard and reply

`j` / `k`: next / previous card. `x`: toggle read. `1`–`9`: choose an option or status. `e` or `Enter`: write a comment. `Esc`: return to the card. `c`: copy its prompt. `g`: General answers. `Ctrl+Enter` (or `Cmd+Enter`): Copy my answers.

The copied reply names every unread id, even when no answers were given:

```text
EASYTALK REPLY: Project status
Not read (bring back next board): D2, F1
Read: Q1, D1, A1
Q1: proceed ★ | “Use the smaller change”
D1: done
A1: “That answers my question”
General: Check the docs too.
```

The ★ records that the user chose the recommendation. If clipboard access is unavailable, the board shows selected reply text for manual copying.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
