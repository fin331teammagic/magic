"""Offline tests for code/describe_run3_features.py."""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import describe_run3_features as d  # noqa: E402
import run_nested_models as nm  # noqa: E402


class DescribeTest(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(0)
        n = 60
        self.frame = pd.DataFrame(
            {c: rng.integers(0, 3, n).astype(float) for c in nm.RUN3}
            | {c: rng.normal(size=n) for c in d.REFERENCE}
        )
        self.frame["guidance_specificity"] = 2.0
        self.frame.loc[0, "guidance_specificity"] = 1.0

    def test_distribution_flags_a_near_constant_variable(self):
        dist = d.describe(self.frame).set_index("variable")
        self.assertEqual(dist.loc["guidance_specificity", "count_2"], 59)
        self.assertEqual(dist.loc["guidance_specificity", "count_-1"], 0)
        self.assertAlmostEqual(dist.loc["guidance_specificity", "modal_share"], 59 / 60, places=3)

    def test_correlations_cover_run3_against_reference(self):
        corr = d.correlations(self.frame)
        self.assertEqual(list(corr.index), list(nm.RUN3))
        self.assertIn("eps_surprise_pct", corr.columns)
        self.assertNotIn("car_0_1_pct", corr.columns)


if __name__ == "__main__":
    unittest.main()
