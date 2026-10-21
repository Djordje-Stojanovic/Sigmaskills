"""Fail a pull request whose body lacks a filled Red test, Review or Skills line.

Ticket 83 PRBODY (2026-10-21). CI calls it with the event payload path:
  python3 .github/scripts/check_pr_body.py "$GITHUB_EVENT_PATH"
It reads the pull request body from the payload. No secrets, no network.
HTML comments (the hints in .github/pull_request_template.md) do not count as text.
"""
import json
import re
import sys

REQUIRED = ("Red test", "Review", "Skills")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
LINE = re.compile(r"^\s*(?:[-*]\s+)?(Red test|Review|Skills):(.*)$")


def missing_lines(body):
    text = COMMENT.sub("", (body or "").replace("\r\n", "\n"))
    filled = set()
    for line in text.split("\n"):
        match = LINE.match(line)
        if match and match.group(2).strip():
            filled.add(match.group(1))
    return [name for name in REQUIRED if name not in filled]


def main(argv):
    if len(argv) != 2:
        print("usage: check_pr_body.py <event-payload.json>")
        return 2
    with open(argv[1], encoding="utf-8") as handle:
        event = json.load(handle)
    missing = missing_lines((event.get("pull_request") or {}).get("body"))
    if missing:
        print("PR body has no filled line for: " + ", ".join(missing) + ".")
        print("Fill each line after its colon. Template: .github/pull_request_template.md")
        return 1
    print("PR body has a filled Red test, Review and Skills line.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
