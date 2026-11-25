"""Tests for code/summarize_llm_screen.py and code/show_transcript.py."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
import show_transcript  # noqa: E402
import summarize_llm_screen as sm  # noqa: E402

SCREEN = ROOT / "outputs" / "exploratory_llm_questions" / "v2.0_gemma4"
SCORES = ROOT / "outputs" / "llm_scores_real" / "q2_2026_llm_scores_v2.0_gemma4_after_cutoff395.csv"


class SummarizeTest(unittest.TestCase):
    @unittest.skipUnless(SCREEN.exists() and SCORES.exists(), "committed run 20 screen not present")
    def test_run20_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "screen"
            shutil.copytree(SCREEN, folder)
            path, sample = sm.summarize(folder)
            text = path.read_text()
            self.assertIn("9a9bc0cb018ccf5a8154cde1725cf4c2ee7ee05e3a4cfad705f297449e6d8f6e", text)
            self.assertIn("CFG_2026-06-30", text)  # parse failure is listed
            self.assertIn("no leads by construction", text)
            self.assertIn("`guidance_specificity` (gemma4)", text)  # low-variation flag
            self.assertEqual(sample["question"].iloc[0], "guidance_revision")
            # IDs and scores only: no free-text column could hold transcript text.
            self.assertEqual(set(sample.columns), {"question", "rounded_mean_score", "event_id", "gemma4"})
            self.assertTrue(sample.groupby(["question", "rounded_mean_score"]).size().le(sm.CALLS_PER_VALUE).all())

    def test_top_questions_puts_leads_first(self):
        leads = pd.DataFrame({"variable": ["a", "b", "c"], "proposed_lead": [False, True, False],
                              "bh_q_within_model": [0.01, 0.2, 0.5]})
        self.assertEqual(sm.top_questions(leads, 2), ["b", "a"])


class ShowTranscriptTest(unittest.TestCase):
    def test_find_and_grep(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calls.jsonl"
            path.write_text(json.dumps({"id": "SYN1", "transcript": "Intro.\nWe raised prices.\nThanks."}) + "\n")
            self.assertIn("raised prices", show_transcript.find_call("SYN1", path))
            self.assertIsNone(show_transcript.find_call("SYN2", path))


if __name__ == "__main__":
    unittest.main()
