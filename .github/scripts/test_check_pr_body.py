"""PR body check, skill lines (ticket 83 PRBODY, 2026-10-22).

A code pull request must name /code-review in its Skills line. A pull request that changes
SKILL.md, CLAUDE.md or AGENTS.md must name /writing-for-agents. The check reads the changed
files from the git history of the checkout (base and head commits in the event payload).
"""
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "check_pr_body.py"


def load_check():
    spec = importlib.util.spec_from_file_location("check_pr_body", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = load_check()

FILLED = "Red test: test_x fails before the fix (1 failed)\nReview: none found, read the diff\n"


def body(skills):
    return FILLED + f"Skills: {skills}\n"


def test_code_pr_without_code_review_is_missing_it():
    assert check.missing_skills(body("tdd, pr"), ["tools/x.py"]) == ["code-review"]


def test_code_pr_naming_code_review_passes():
    assert check.missing_skills(body("tdd, code-review, pr"), ["tools/x.py"]) == []


def test_slash_form_counts_as_naming_the_skill():
    assert check.missing_skills(body("/tdd, /code-review, /pr"), ["tools/x.py"]) == []


def test_none_invoked_does_not_name_code_review():
    assert check.missing_skills(body("none invoked."), ["tools/x.js"]) == ["code-review"]


@pytest.mark.parametrize("paths", [["tests/test_x.py"], ["test/sigmadeeplook/test_v2.py", "README.md"],
                                   ["lib/__tests__/x.test.mjs"], ["src/a.spec.ts", "pkg/b_test.go"]])
def test_test_only_pr_needs_no_code_review(paths):
    assert check.missing_skills(body("pr"), paths) == []


@pytest.mark.parametrize("paths", [["scripts/run-tests.js"], ["test/helpers.js"]])
def test_a_runner_or_helper_in_the_test_folder_needs_code_review(paths):
    assert check.missing_skills(body("pr"), paths) == ["code-review"]


def test_a_test_beside_product_code_still_needs_code_review():
    assert check.missing_skills(body("pr"), ["test/x.test.js", "src/x.js"]) == ["code-review"]


def test_docs_only_pr_needs_no_code_review():
    assert check.missing_skills(body("pr"), ["README.md"]) == []


@pytest.mark.parametrize("path", ["skills/x/SKILL.md", "CLAUDE.md", "docs/AGENTS.md"])
def test_skill_or_agent_file_needs_writing_for_agents(path):
    assert check.missing_skills(body("pr, code-review"), [path]) == ["writing-for-agents"]


def test_skill_file_naming_writing_for_agents_passes():
    assert check.missing_skills(body("pr, writing-for-agents"), ["CLAUDE.md"]) == []


def test_code_and_skill_files_name_both_skills():
    assert check.missing_skills(body("pr"), ["a.py", "AGENTS.md"]) == ["code-review", "writing-for-agents"]


@pytest.mark.parametrize("path", ["tools/run.bat", "tools/run.cmd", "tools/run.sh", "tools/run.zsh"])
def test_windows_and_shell_scripts_count_as_code(path):
    assert check.missing_skills(body("pr"), [path]) == ["code-review"]


def test_changed_files_lists_the_pull_request_diff(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        done = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)
        return done.stdout.strip()

    git("init", "-q", "-b", "main")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "test")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    git("add", "a.txt")
    git("commit", "-q", "-m", "base")
    base = git("rev-parse", "HEAD")
    git("checkout", "-q", "-b", "feature")
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git("add", "x.py")
    git("commit", "-q", "-m", "feature")
    head = git("rev-parse", "HEAD")
    pr = {"base": {"sha": base}, "head": {"sha": head}}
    assert check.changed_files(pr, cwd=repo) == ["x.py"]


def test_changed_files_keeps_unicode_names_and_both_sides_of_a_rename(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        done = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)
        return done.stdout.strip()

    git("init", "-q", "-b", "main")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "test")
    (repo / "CLAUDE.md").write_text("notes\n", encoding="utf-8")
    git("add", "CLAUDE.md")
    git("commit", "-q", "-m", "base")
    base = git("rev-parse", "HEAD")
    git("checkout", "-q", "-b", "feature")
    git("mv", "CLAUDE.md", "notes.txt")
    (repo / "café.py").write_text("x = 1\n", encoding="utf-8")
    git("add", "café.py")
    git("commit", "-q", "-m", "feature")
    head = git("rev-parse", "HEAD")
    pr = {"base": {"sha": base}, "head": {"sha": head}}
    assert sorted(check.changed_files(pr, cwd=repo)) == sorted(["CLAUDE.md", "café.py", "notes.txt"])


def run_main(tmp_path, monkeypatch, pr_body, files):
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps({"pull_request": {"body": pr_body, "base": {"sha": "a" * 40}, "head": {"sha": "b" * 40}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(check, "changed_files", lambda pr, cwd=None: files)
    return check.main(["check_pr_body.py", str(event)])


def test_main_fails_a_code_pr_without_code_review(tmp_path, monkeypatch, capsys):
    assert run_main(tmp_path, monkeypatch, body("tdd, pr"), ["tools/x.py"]) == 1
    assert "code-review" in capsys.readouterr().out


def test_main_passes_a_code_pr_with_code_review(tmp_path, monkeypatch):
    assert run_main(tmp_path, monkeypatch, body("tdd, code-review, pr"), ["tools/x.py"]) == 0


def test_main_still_fails_a_body_without_the_lines(tmp_path, monkeypatch):
    assert run_main(tmp_path, monkeypatch, "Skills: tdd, code-review\n", ["README.md"]) == 1


def test_main_fails_when_the_changed_files_cannot_be_read(tmp_path, monkeypatch, capsys):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"body": body("pr")}}), encoding="utf-8")

    def broken(pr, cwd=None):
        raise RuntimeError("the event has no base or head commit")

    monkeypatch.setattr(check, "changed_files", broken)
    assert check.main(["check_pr_body.py", str(event)]) == 1
    assert "no base or head commit" in capsys.readouterr().out
