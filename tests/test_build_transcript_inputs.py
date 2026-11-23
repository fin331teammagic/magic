"""Offline tests for code/build_transcript_inputs.py, on invented data only."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import build_transcript_inputs as b  # noqa: E402


def cohort_frame():
    return pd.DataFrame(
        {
            "event_id": ["AAA_2026-06-30", "BBB_2026-06-30", "CCC_2026-06-30",
                         "DDD_2026-06-30", "EEE_2026-03-31", "FFF_2026-06-30"],
            "ticker": ["AAA", "BB.B", "CCC", "DDD", "EEE", "FFF"],
            "cik": ["0000000001", "", "0000000003", "0000000004", "0000000005", "0000000006"],
            "fiscal_period_end": ["2026-06-30"] * 4 + ["2026-03-31", "2026-06-30"],
            "earnings_timestamp": [
                "2026-07-20T16:05:00-04:00",  # call next day
                "2026-07-21T07:00:00-04:00",  # ticker match only
                "2026-07-01T16:00:00-04:00",  # early 8-K; call on 07-25
                "2026-08-20T16:00:00-04:00",  # after data end
                "2026-04-24T07:00:00-04:00",  # before training cutoff
                "2026-07-22T07:00:00-04:00",  # firm absent
            ],
        }
    )


def calls_frame():
    return pd.DataFrame(
        {
            "keydevid": [10, 11, 20, 30, 40, 50],
            "call_date": ["2026-07-21", "2026-07-20", "2026-07-21", "2026-07-25",
                          "2026-04-28", "2026-04-24"],
            "cik": ["0000000001", "0000000001", "0000000099", "0000000003",
                    "0000000004", "0000000005"],
            "tic": ["AAA", "AAA", "BBB", "CCC", "DDD", "EEE"],
            "headline": ["AAA, Q2 2026 Earnings Call", "AAA, Q2 2026 Pre Recorded Earnings Call",
                         "BBB, Q2 2026 Earnings Call", "CCC, Q2 2026 Earnings Call",
                         "DDD, Q1 2026 Earnings Call", "EEE, Q1 2026 Earnings Call"],
            "n_words": [100, 50, 200, 300, 400, 500],
        }
    )


class BuildTranscriptInputsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.cohort_path = root / "cohort.csv"
        cohort_frame().to_csv(self.cohort_path, index=False)
        self.data = root / "data"
        self.data.mkdir()
        calls_frame().to_csv(self.data / b.CALLS_FILE, index=False)
        pd.DataFrame(
            {"keydevid": [10, 11, 20, 30, 40, 50],
             "full_text": [f"SYNTHETIC CALL {k}" for k in (10, 11, 20, 30, 40, 50)]}
        ).to_parquet(self.data / b.TEXT_FILE)
        self.out = root / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def matches(self):
        cohort = b.load_cohort(self.cohort_path)
        calls = b.load_calls(self.data / b.CALLS_FILE)
        return b.match_events(cohort, calls, max_lag_days=3).set_index("event_id")

    def test_statuses_and_keys(self):
        m = self.matches()
        self.assertEqual(m.loc["AAA_2026-06-30", "match_status"], "matched")
        self.assertEqual(m.loc["AAA_2026-06-30", "keydevid"], 10)  # pre-recorded skipped
        self.assertEqual(m.loc["AAA_2026-06-30", "days_from_earnings"], 1)
        self.assertEqual(m.loc["BBB_2026-06-30", "match_key"], "ticker")
        self.assertEqual(m.loc["CCC_2026-06-30", "match_status"], "matched_by_period_end")
        self.assertEqual(m.loc["CCC_2026-06-30", "keydevid"], 30)
        self.assertEqual(m.loc["DDD_2026-06-30", "match_status"], "unmatched_after_data_end")
        self.assertEqual(m.loc["FFF_2026-06-30", "match_status"],
                         "unmatched_firm_not_in_transcripts")
        self.assertEqual(len(m), 6)  # unmatched events are kept

    def test_training_cutoff_flag(self):
        m = self.matches()
        self.assertTrue(m.loc["AAA_2026-06-30", "after_training_cutoff"])
        self.assertFalse(m.loc["EEE_2026-03-31", "after_training_cutoff"])
        self.assertTrue(pd.isna(m.loc["DDD_2026-06-30", "after_training_cutoff"]))

    def test_main_writes_jsonl_for_matched_only(self):
        b.main(["--cohort", str(self.cohort_path), "--data-dir", str(self.data),
                "--out-dir", str(self.out)])
        rows = [json.loads(line) for line in (self.out / "q2_2026_calls.jsonl").read_text().splitlines()]
        self.assertEqual({r["id"] for r in rows},
                         {"AAA_2026-06-30", "BBB_2026-06-30", "CCC_2026-06-30", "EEE_2026-03-31"})
        match = pd.read_csv(self.out / "q2_2026_transcript_match.csv")
        self.assertNotIn("full_text", match.columns)
        self.assertEqual(len(match), 6)

    def test_after_cutoff_only(self):
        b.main(["--cohort", str(self.cohort_path), "--data-dir", str(self.data),
                "--out-dir", str(self.out), "--after-cutoff-only"])
        ids = {json.loads(line)["id"] for line in
               (self.out / "q2_2026_calls_after_cutoff.jsonl").read_text().splitlines()}
        self.assertNotIn("EEE_2026-03-31", ids)
        self.assertIn("AAA_2026-06-30", ids)


if __name__ == "__main__":
    unittest.main()
