"""Ticket 83 M18: the fixed-position schedule in the sigmadeeplook references is the one dl_textx.landmarks() prints.

The schedule is one meaning; two reference files state it. Both must carry the same words, and the words must
match the code: the record numbers 1-5, 10, 20, 25, 30, 40, 50, 75, 100, then the middle and the last record.
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "sigmadeeplook" / "scripts"
REFERENCES = ROOT / "sigmadeeplook" / "references"
SCHEDULE = "(#1-5, 10, 20, 25, 30, 40, 50, 75, 100 ... and the middle)"
LISTED = (1, 2, 3, 4, 5, 10, 20, 25, 30, 40, 50, 75, 100)


class FixedPositionSchedule(unittest.TestCase):
    def test_each_reference_that_lists_the_schedule_states_it_the_same_way(self):
        for name in ("data.md", "office.md"):
            text = (REFERENCES / name).read_text(encoding="utf-8")
            self.assertIn(SCHEDULE, text, name)

    def test_the_schedule_is_the_one_the_code_prints(self):
        sys.path.insert(0, str(SCRIPTS))
        try:
            import dl_textx
        finally:
            sys.path.pop(0)
        major, minor = dl_textx.landmarks(1000)
        positions = set(major) | set(minor)
        for k in LISTED + (500, 1000):
            self.assertIn(k, positions, k)
        self.assertIn(500, major, "the middle record is a major mark")
        self.assertIn(1000, major, "the last record is a major mark")


if __name__ == "__main__":
    unittest.main()
