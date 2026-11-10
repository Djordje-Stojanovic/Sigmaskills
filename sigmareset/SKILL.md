---
name: sigmareset
description: Use when asked for sigmareset, or when a repo, a machine or a whole setup is bloated and the owner lost track of what exists. Lists every product, the owner says keep or kill, the agent deletes the rest. Do not use for one bug (SigmaReview) or one refactor (SigmaRefactor).
---

# SigmaReset

Bring a bloated setup back to what the owner really uses. It is Musk's five steps, run on products instead of files.

Why it works: principles do not say what to delete; the owner's purpose does. An agent cannot guess the purpose, and an owner cannot review 100,000 lines. So the agent turns the files into a short list of products, the owner answers keep or kill, and the rest follows from that.

Write everything the owner reads in plain English: short sentences, the answer first, letters to pick.

## 1. Purposes

Ask what the setup exists for. Three purposes at most. Offer your own guess from what you see, so the owner can answer "yes".

## 2. Inventory: look inside first

Sweep everything in scope: repos, folders, services, commands, scheduled jobs, models, installed apps, open issues, skills and instruction files. Open each thing before you judge it: size, history, whether a copy exists elsewhere, last change, the first lines of its README. A name alone tells you nothing; an "old folder" may hold the only copy of real work.

Group what you find into **products**: things the owner would recognise by name (a site, a channel, a tool, a game). Aim for 15 to 30. For each product write one line:

- what it does, in plain words;
- what it costs: lines, GB, memory, money, running services;
- the use you can prove (shell history, logs, last commit). Write "not measured" when you have no proof;
- your pick: keep, kill or the owner's word.

Also measure the waste as numbers, each with its command: how many commands exist against how many are used, lines in version control against lines of real product, how often the same fact is written in code. These numbers are the before; you measure them again at the end.

## 3. Who decides what

- **The agent deletes and tells after:** its own temp files, caches, copies that can be downloaded again.
- **The agent deletes without asking, under a kept product:** code, tests, docs and config that nothing runs. Version history is the undo.
- **The owner decides, one by one:** a product; anything the owner made; models and other large downloads; chats and other history; anything that cannot be recovered.

Before the owner decides on something that exists in one place only, say so, and offer to save a copy first.

## 4. Ask in rounds

At most 12 products per round, the most costly first, as a table with your pick. "A" accepts every pick; otherwise the owner answers by number. Work that does not depend on an answer continues while you wait.

## 5. Delete, then simplify

1. Remove each killed product in every place it lives: code, config, running service, data, docs, tests, monitors, issues.
2. Under each kept product, delete what nothing runs.
3. Simplify what is left: one copy of each fact, settings in one file.
4. Speed it up.
5. Automate last.

After each step, measure the numbers again and show before and after. Land changes by the repo's own rules.

## 6. The gate that keeps it clean

A new thing enters only if the owner can name (a) which purpose it serves and (b) what was missing last week without it. A video or a post that recommends it is not a reason. Every addition names what it deletes.

## The map

Keep one file, at most 150 lines: purposes, the numbers, the product table, what is decided, what waits for the owner, where things are, what is not checked. A new line replaces an old one. It is the handoff: a new agent reads it first and continues.

## Final response

1. The numbers, before and after.
2. What was killed and what was kept.
3. What still waits for the owner.
4. What you did not check.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
