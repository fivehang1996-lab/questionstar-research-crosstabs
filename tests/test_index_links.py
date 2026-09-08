import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "add_internal_index_links.py"
SPEC = importlib.util.spec_from_file_location("add_internal_index_links", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class QuestionRowTests(unittest.TestCase):
    def test_rows_match_workbook_block_layout(self):
        analysis = {
            "rows": [
                {"q_index": 1, "kind": "total"},
                {"q_index": 1, "kind": "percent"},
                {"q_index": 1, "kind": "percent"},
                {"q_index": 2, "kind": "total"},
                {"q_index": 2, "kind": "mean"},
                {"q_index": 2, "kind": "percent"},
            ]
        }
        self.assertEqual(MODULE.question_rows(analysis), [7, 18])


if __name__ == "__main__":
    unittest.main()
