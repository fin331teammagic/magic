"""Offline tests for code/build_dictionary_features.py on invented components."""

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import build_dictionary_features as bdf  # noqa: E402


def write_inputs(root):
    pd.DataFrame({
        "Word": ["GOOD", "BAD", "MAYBE", "STRONG"],
        "Negative": [0, 2009, 0, 0], "Positive": [2009, 0, 0, 2009],
        "Uncertainty": [0, 0, 2009, 0],
    }).to_csv(root / "dict.csv", index=False)
    pd.DataFrame({
        "event_id": ["AAA_2026-06-30", "BBB_2026-06-30", "CCC_2026-06-30"],
        "ticker": ["AAA", "BBB", "CCC"], "keydevid": [1.0, 2.0, None],
        "call_date": ["2026-07-21", "2026-07-22", None],
        "match_status": ["matched", "matched", "unmatched_firm_not_in_transcripts"],
        "after_training_cutoff": [True, True, None],
    }).to_csv(root / "match.csv", index=False)
    rows = [
        # call 1: operator, prepared (good good bad), analyst (congrats maybe), answer (strong)
        (1, 1, "Presentation Operator Message", "Operator", "Welcome"),
        (1, 2, "Presenter Speech", "Executives", "good good bad quarter"),
        (1, 3, "Question", "Analysts", "Congrats team maybe"),
        (1, 4, "Answer", "Executives", "strong"),
        # call 2: no analyst questions
        (2, 1, "Presenter Speech", "Executives", "bad bad results"),
    ]
    pd.DataFrame(rows, columns=bdf.COMPONENT_COLUMNS).to_parquet(root / "comp.parquet")


class BuildDictionaryFeaturesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write_inputs(self.root)
        self.out = bdf.build(self.root / "match.csv", self.root / "comp.parquet",
                             self.root / "dict.csv").set_index("event_id")

    def tearDown(self):
        self.tmp.cleanup()

    def test_known_values(self):
        a = self.out.loc["AAA_2026-06-30"]
        # whole call: welcome good good bad quarter congrats team maybe strong = 9 words
        self.assertEqual(a["transcript_word_count"], 9)
        self.assertAlmostEqual(a["transcript_sentiment"], (3 - 1) / 9)
        self.assertAlmostEqual(a["uncertainty_word_proportion"], 1 / 9)
        self.assertAlmostEqual(a["management_prepared_sentiment"], (2 - 1) / 4)
        self.assertAlmostEqual(a["analyst_question_sentiment"], 0.0)
        self.assertAlmostEqual(a["management_qa_sentiment"], 1.0)
        self.assertEqual(a["congratulations_mentioned"], 1)
        self.assertEqual(a["section_status"], "complete")

    def test_missing_sections_stay_missing(self):
        b = self.out.loc["BBB_2026-06-30"]
        self.assertTrue(pd.isna(b["analyst_question_sentiment"]))
        self.assertTrue(pd.isna(b["congratulations_mentioned"]))
        self.assertIn("missing_analyst_questions", b["section_status"])

    def test_unmatched_events_and_text_are_not_written(self):
        self.assertNotIn("CCC_2026-06-30", self.out.index)
        self.assertNotIn("componenttext", self.out.columns)


if __name__ == "__main__":
    unittest.main()
