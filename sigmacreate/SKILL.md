---
name: sigmacreate
description: 'Use when asked for sigmacreate or to make, write or install a new skill: a public skill to publish, with no personal data, or a local skill for one project, repo or machine. Ends with the skill installed and picked up. Do not use for a correction given twice (SigmaCorrect).'
---

# SigmaCreate

Make one skill and leave it working: written, installed, and picked up by a fresh agent. A skill is the instructions an agent loads when its description matches the request. The description is read on every turn; the body only when the skill runs. So the description decides when the skill fires, and every line of the body has to change what the agent does.

There are two routes:

- **Public.** A skill strangers install, like the Sigma skills. It names no person, machine, account, host or key. It ends in the skill repo it is published from.
- **Local.** A skill for one project, one repo or one machine. It may name that place's own paths, commands and words. It ends where that place's agent loads skills.

## 1. Pick the route and find out

Take the route from the request. "Publish", "for everyone", "a Sigma skill" or a skill repo as the target mean public. "For this repo", "on this machine", or a path or command of this place mean local. Ask only when nothing says which.

Then find out before you ask. Read, in this order:

1. The request and the chat. A workflow already done in this chat is the best draft: its steps, its tools, and every correction the person made.
2. The target repo's `AGENTS.md` or `CLAUDE.md`, and two of its existing skills. They set the house style and the lists a new skill must join.
3. The skills already installed. When one already does the job, improve that one instead of adding a second.

Ask one message at most, holding only what none of these showed. Usually that is the words people will type to start it, and what done looks like.

**Done when** you can write the route, the name, three prompts that must start the skill, and one near prompt that must start a different one.

## 2. Write it

One folder, named like the skill: lowercase, hyphens, at most 64 characters. Inside, one `SKILL.md`:

```markdown
---
name: <folder name>
description: '<what it does>. Use when <the words people say>. Do not use for <the nearest neighbour> (<its name>).'
---

# <Title>

<One paragraph: what it makes, and when it is done.>

## 1. <First step>
<What to do.> **Done when** <a check anyone can see>.
```

- **The description** is at most 1024 characters, quoted. Put the trigger words first, one per distinct case: two words for the same case cost load and add nothing. It says when to use the skill, never the steps: an agent that reads a summary follows the summary.
- **Each step** ends on a done check you can observe: a file exists, a command prints a line, a count is zero. "Understood" is not a check.
- **Say the target.** "Write one-line comments" works; "do not write long comments" puts long comments in the agent's mind.
- **Cut every sentence the agent would obey anyway.** It is capable; write what it cannot guess: the house rule, the reason behind a choice, the trap no config shows.
- **Split only where it earns it.** A part only some runs need goes to `references/<part>.md`, with a line in `SKILL.md` saying when to read it. A step that must give the same result every time becomes a script. Everything else stays in the one file.

When the target repo has its own shape (an `agents/openai.yaml`, a personal block, a description pattern), follow it: the house rule wins.

**Done when** the folder holds `SKILL.md` plus only the files a step points to.

## 3. Test it on a fresh agent

Give a fresh agent, with no memory of this chat, one of the three prompts and the skill. Then give the same prompt to an agent without it. Keep a line only if the two answers differ because of it. When both agents do the same, the line was a no-op: delete it. When the agent with the skill goes wrong, fix the line it misread and run the prompt again.

**Done when** one prompt run with the skill does the job, and the near prompt does not start it.

## 4. Public route: the clean check

A public skill holds no personal data. Collect what would identify this person and machine, including every host in `~/.ssh/config`, then search the skill folder for it and for the usual shapes:

```bash
skill=<skill folder>; me=$(mktemp)
{ git config user.name; git config user.email; gh api user -q .login; hostname; whoami
  awk '/^Host /{for(i=2;i<=NF;i++)print $i}' ~/.ssh/config; } 2>/dev/null | grep -vE '^$|[*?]' | sort -u > "$me"
grep -rniwE "$(paste -sd'|' "$me")" "$skill"   # one pattern: Git Bash grep aborts on -i with -f
grep -rniE '\b[A-Za-z]:[/\][[:alnum:]]|/home/[a-z]|/Users/[a-z]|[[:alnum:]._%+-]+@[[:alnum:].-]+\.[a-z]{2,}|\b(10(\.[0-9]{1,3}){3}|192\.168(\.[0-9]{1,3}){2}|172\.(1[6-9]|2[0-9]|3[01])(\.[0-9]{1,3}){2})\b|ghp_|github_pat_|sk-[A-Za-z0-9]|AKIA|BEGIN [A-Z ]*PRIVATE KEY' "$skill"
```

The drive pattern flags every Windows path (`C:\Users\`, `C:/Users/`, `D:\work\`), not only home folders.

Run the target repo's own private-name check too, if it has one. Replace each hit with a placeholder (`<project>`, `~/repos/<name>`, `you@example.com`) or a word that fits anyone.

**Done when** both searches print nothing, or each line left is a placeholder you can name.

## 5. Install and prove it

**Public:** list the skill everywhere the repo's `AGENTS.md` says a new skill goes (manifest, tests, README, install docs, changelog), run the repo's test command, and ship it through the repo's own flow. Then install it with the repo's installer, or copy the folder to `~/.agents/skills/<name>/` and `~/.claude/skills/<name>/`.

**Local:** copy the folder where the agent of that place loads skills:

| Agent | One project or repo | One machine |
|---|---|---|
| Claude Code | `.claude/skills/<name>/` | `~/.claude/skills/<name>/` |
| Codex, pi, and most others | `.agents/skills/<name>/` | `~/.agents/skills/<name>/` |

The Sigma installer's host list (`registry/agent-hosts.json` in the Sigmaskills repo) holds the folders of the other agents. A project skill goes into that repo's git with the change it belongs to; a machine skill stays on the machine.

Prove that a fresh agent sees it. Start one in the target folder with closed input, and ask for its skills:

```bash
claude -p "List the names of the skills you can use, one per line." < /dev/null | grep -x '<name>'
codex exec "List the names of the skills you can use, one per line." < /dev/null | grep '<name>'
```

**Done when** the name comes back from a fresh agent on every machine the skill is meant for.

## Report

The name to type, the route, where it landed, the three prompts and the near one, the clean check output (public), and the proof line per machine.

## Sources

Built from five skill-creator skills, rewritten, no text copied: Matt Pocock's [writing-for-agents](https://github.com/mattpocock/skills/blob/main/skills/productivity/writing-for-agents/SKILL.md) and [write-a-skill](https://github.com/mattpocock/skills/blob/ab7196a1584ac60688aeb63cf0b56a5114c4a6f3/skills/productivity/write-a-skill/SKILL.md), Anthropic's [skill-creator](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md), obra's [writing-skills](https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md) and OpenAI's [skill-creator](https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md).

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
