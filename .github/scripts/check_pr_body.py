"""Fail a pull request whose body lacks a filled Red test, Review or Skills line, or whose
Skills line lacks a skill its changed files need.

Ticket 83 PRBODY (2026-10-21; skill rule 2026-10-22). CI calls it with the event payload path:
  python3 .github/scripts/check_pr_body.py "$GITHUB_EVENT_PATH"
The pull request body comes from the payload. The changed files come from the git history of the
checkout (fetch-depth 0): the base and head commits in the payload. No secrets, no network.
HTML comments (the hints in .github/pull_request_template.md) do not count as text.
A code pull request must name code-review; a pull request whose code files are all tests does not (owner
2026-10-29: test-only changes skip the review bot). A pull request that changes SKILL.md, CLAUDE.md or
AGENTS.md must name writing-for-agents. A skill counts when it is named, with or without the slash.
"""
import json
import re
import subprocess
import sys

REQUIRED = ("Red test", "Review", "Skills")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
LINE = re.compile(r"^\s*(?:[-*]\s+)?(Red test|Review|Skills):(.*)$")
CODE_EXTENSIONS = {
    "py", "js", "mjs", "cjs", "jsx", "ts", "tsx", "sh", "bash", "zsh", "bat", "cmd", "ps1", "psm1",
    "go", "rs", "sql", "java", "kt", "c", "h", "cpp", "cc", "cs", "rb", "php",
}
SKILL_FILES = {"skill.md", "claude.md", "agents.md"}


def missing_lines(body):
    text = COMMENT.sub("", (body or "").replace("\r\n", "\n"))
    filled = set()
    for line in text.split("\n"):
        match = LINE.match(line)
        if match and match.group(2).strip():
            filled.add(match.group(1))
    return [name for name in REQUIRED if name not in filled]


def required_skills(paths):
    needed = []
    if any(is_code_file(path) and not is_test_file(path) for path in paths):
        needed.append("code-review")
    if any(path.rsplit("/", 1)[-1].lower() in SKILL_FILES for path in paths):
        needed.append("writing-for-agents")
    return needed


def is_code_file(path):
    name = path.rsplit("/", 1)[-1]
    return "." in name and name.rsplit(".", 1)[-1].lower() in CODE_EXTENSIONS


def is_test_file(path):   # by its name: test_x.py, test-x.sh, x_test.go, x.test.mjs, x.spec.ts. A runner or helper in tests/ is code.
    name = path.rsplit("/", 1)[-1].lower()
    return name.startswith(("test_", "test-")) or re.search(r"(_test|\.test|\.spec)\.[^.]+$", name) is not None


def skills_text(body):
    text = COMMENT.sub("", (body or "").replace("\r\n", "\n"))
    values = []
    for line in text.split("\n"):
        match = LINE.match(line)
        if match and match.group(1) == "Skills":
            values.append(match.group(2))
    return " ".join(values)


def named(skill, text):
    return re.search(r"(?<![\w-])/?" + re.escape(skill) + r"(?![\w-])", text) is not None


def missing_skills(body, paths):
    text = skills_text(body)
    return [skill for skill in required_skills(paths) if not named(skill, text)]


def changed_files(pr, cwd=None):
    base = (pr.get("base") or {}).get("sha")
    head = (pr.get("head") or {}).get("sha")
    if not base or not head:
        raise RuntimeError("the event has no base or head commit")
    # -z: names come back raw and NUL-separated (no quoting of non-ASCII names).
    # --no-renames: a rename lists the old path too, so moving SKILL.md away still counts.
    done = subprocess.run(
        ["git", "diff", "-z", "--no-renames", "--name-only", f"{base}...{head}"],
        cwd=cwd, capture_output=True,
    )
    if done.returncode != 0:
        raise RuntimeError("git diff failed: " + done.stderr.decode("utf-8", "replace").strip())
    return [name for name in done.stdout.decode("utf-8", "surrogateescape").split("\0") if name]


def main(argv):
    if len(argv) != 2:
        print("usage: check_pr_body.py <event-payload.json>")
        return 2
    with open(argv[1], encoding="utf-8") as handle:
        event = json.load(handle)
    pr = event.get("pull_request") or {}
    missing = missing_lines(pr.get("body"))
    if missing:
        print("PR body has no filled line for: " + ", ".join(missing) + ".")
        print("Fill each line after its colon. Template: .github/pull_request_template.md")
        return 1
    try:
        paths = changed_files(pr)
    except RuntimeError as error:
        print("Could not read the changed files: " + str(error) + ".")
        return 1
    lacks = missing_skills(pr.get("body"), paths)
    if lacks:
        print("Skills line lacks: " + ", ".join("/" + skill for skill in lacks) + ".")
        print("This PR changes files that need them. Name each skill you used. Template: .github/pull_request_template.md")
        return 1
    print("PR body has a filled Red test, Review and Skills line, with the skills its files need.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
