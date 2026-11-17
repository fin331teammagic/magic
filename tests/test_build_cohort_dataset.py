"""Tests for the pure join of Gus's checkpoint files into the cohort file."""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from build_cohort_dataset import build_cohort  # noqa: E402


def _frames():
    keys = pd.DataFrame({"event_id": ["A_2026-06-30", "B_2026-06-30"], "ticker": ["A", "B"],
                         "fiscal_period_end": ["2026-06-30", "2026-06-30"]})
    events = keys.assign(earnings_timestamp=["2026-07-20T08:00:00-04:00", "2026-07-21T16:30:00-04:00"],
                         eps_surprise_pct=[5.0, np.nan], data_status="cohort")
    study = keys.assign(car_0_1_pct=[1.5, np.nan], data_status="cohort")
    features = keys.assign(log_market_cap=[24.0, 25.0], data_status="cohort")
    return events, study, features


class BuildCohortTests(unittest.TestCase):
    def test_join_keeps_every_event_and_blanks(self):
        out = build_cohort(*_frames())
        self.assertEqual(len(out), 2)
        self.assertEqual(list(out["event_id"]), ["A_2026-06-30", "B_2026-06-30"])
        self.assertTrue(pd.isna(out.loc[1, "car_0_1_pct"]))  # blank stays blank, never 0
        self.assertTrue(pd.isna(out.loc[1, "eps_surprise_pct"]))
        self.assertIn("log_market_cap", out.columns)
        self.assertEqual(list(out.columns).count("data_status"), 1)

    def test_duplicate_event_ids_are_rejected(self):
        events, study, features = _frames()
        study = pd.concat([study, study.iloc[[0]]])
        with self.assertRaises(ValueError):
            build_cohort(events, study, features)

    def test_ticker_disagreement_is_rejected(self):
        events, study, features = _frames()
        features.loc[0, "ticker"] = "Z"
        with self.assertRaises(ValueError):
            build_cohort(events, study, features)

    def test_different_event_sets_are_rejected(self):
        events, study, features = _frames()
        with self.assertRaises(ValueError):
            build_cohort(events, study.iloc[:1], features)

    def test_committed_cohort_matches_inputs(self):
        path = ROOT / "outputs" / "q2_2026_cohort.csv"
        if not path.exists():
            self.skipTest("cohort file not built")
        cohort = pd.read_csv(path)
        events = pd.read_csv(ROOT / "inputs" / "q2_2026_events.csv")
        self.assertEqual(set(cohort["event_id"]), set(events["event_id"]))
        self.assertTrue(cohort["event_id"].is_unique)


if __name__ == "__main__":
    unittest.main()
