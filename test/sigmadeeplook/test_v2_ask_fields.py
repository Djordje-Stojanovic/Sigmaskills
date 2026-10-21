"""--ask must not answer a question from a field that names only one of its words (ticket 83, K29a-1).

A Claude Code transcript holds fields called hookErrors and shape.tools. A question about tool errors names both words
("tool" and "error"), but neither field names both, so neither may answer it. The fixtures below are small and made here.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import run  # noqa: E402


def write_jsonl(path, records):
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


# No field holds tool errors. hookErrors (count) and shape.tools (count) each name only one of the two words.
TRANSCRIPT = [
    {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "is_error": True, "content": "x"}]}},
    {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Bash"}]}, "shape": {"tools": ["Bash", "Read"]}},
    {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Edit"}]}, "shape": {"tools": ["Edit"]}},
    {"type": "system", "subtype": "stop_hook_summary", "hookErrors": []},
    {"type": "system", "subtype": "stop_hook_summary", "hookErrors": ["boom"]},
]

# The same transcript with a field that names both words: toolErrors 1 and 2 make a sum of 3.
TRANSCRIPT_WITH_TOOL_ERRORS = [
    dict(TRANSCRIPT[0]),
    dict(TRANSCRIPT[1], toolErrors=1),
    dict(TRANSCRIPT[2], toolErrors=2),
    dict(TRANSCRIPT[3]),
    dict(TRANSCRIPT[4]),
]


class AskFieldChoice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_askfields_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def ask(self, name, records, question):
        p = self.tmp / f"{name}.jsonl"
        write_jsonl(p, records)
        out = self.tmp / f"out_{name}"
        r = run([str(p), "--out", str(out), "--no-tools", "--ask", question])
        self.assertEqual(r.returncode, 0, r.stderr[-1500:])
        return r.stdout

    @staticmethod
    def answer_lines(text):
        return [ln for ln in text.splitlines() if ln.startswith("Answer")]

    def test_tool_errors_are_not_taken_from_a_field_that_names_one_word(self):
        out = self.ask("no_tool_errors", TRANSCRIPT, "How many tool errors?")
        answer = " ".join(self.answer_lines(out))
        self.assertNotIn("shape.tools", answer)
        self.assertNotIn("hookErrors", answer)
        self.assertIn("No table answers this exactly", out)

    def test_max_of_tool_errors_is_not_taken_from_a_hook_field(self):
        out = self.ask("max_tool_errors", TRANSCRIPT, "What is the max tool error?")
        answer = " ".join(self.answer_lines(out))
        self.assertNotIn("hookErrors", answer)
        self.assertNotIn("shape.tools", answer)

    def test_a_field_that_names_both_words_still_answers(self):
        out = self.ask("with_tool_errors", TRANSCRIPT_WITH_TOOL_ERRORS, "How many tool errors?")
        self.assertIn("Answer: sum of toolErrors = 3 ", out)


if __name__ == "__main__":
    unittest.main()
