"""Offline tests for code/compare_llm_runs.py."""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import compare_llm_runs as c  # noqa: E402


def scores(values, ids=("A", "B", "C", "D")):
    frame = pd.DataFrame({"id": list(ids), "status": "scored", "parse_status": "ok"})
    for name in c.RUN3:
        frame[name] = values
    return frame


class CompareTest(unittest.TestCase):
    def test_identical_runs_agree_perfectly(self):
        run = scores([0, 1, 2, 1])
        result = c.compare(run, run).set_index("variable")
        self.assertTrue((result["exact_agreement"] == 1).all())
        self.assertAlmostEqual(result.loc["qa_evasiveness", "weighted_kappa"], 1.0)

    def test_nulls_and_disagreement_are_counted(self):
        first = scores([0, 1, 2, np.nan])
        second = scores([0, 1, 0, 1])
        result = c.compare(first, second).set_index("variable")
        self.assertEqual(result.loc["guidance_revision", "exact_agreement"], 0.5)
        self.assertEqual(result.loc["guidance_revision", "null_in_one_run_only"], 1)
        self.assertLess(result.loc["guidance_revision", "weighted_kappa"], 1)

    def test_kappa_is_zero_for_independent_ratings(self):
        self.assertAlmostEqual(c.weighted_kappa([0, 0, 1, 1], [0, 1, 0, 1]), 0.0)


if __name__ == "__main__":
    unittest.main()
