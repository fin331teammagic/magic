"""Offline tests for code/car_255_robustness.py with a planted FF5 model."""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import car_255_robustness as r  # noqa: E402


def planted(n_days=420, day0_pos=400, ar0=0.05, ar1=0.02, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-01", periods=n_days)
    factors = pd.DataFrame(rng.normal(0, 0.01, (n_days, 5)), index=dates, columns=r.FACTORS)
    ret = 0.0005 + factors.to_numpy() @ np.array([1.2, 0.3, -0.2, 0.1, 0.05]) + rng.normal(0, 0.0003, n_days)
    ret[day0_pos] += ar0
    ret[day0_pos + 1] += ar1
    return pd.Series(ret, index=dates), factors, dates[day0_pos]


class Car255Test(unittest.TestCase):
    def test_recovers_planted_abnormal_returns_on_full_window(self):
        returns, factors, day0 = planted()
        car, nobs = r.car_0_1(returns, factors, day0, "full")
        self.assertEqual(nobs, 255)
        self.assertAlmostEqual(car, 7.0, delta=0.15)

    def test_easy_es_mode_truncates_by_calendar_days(self):
        returns, factors, day0 = planted()
        _, nobs = r.car_0_1(returns, factors, day0, "easy_es")
        self.assertLess(nobs, 255)
        self.assertGreater(nobs, 150)

    def test_too_little_history_returns_missing(self):
        returns, factors, day0 = planted(n_days=200, day0_pos=150)  # 90 estimation days < 100
        car, _ = r.car_0_1(returns, factors, day0, "full")
        self.assertTrue(np.isnan(car))


if __name__ == "__main__":
    unittest.main()
