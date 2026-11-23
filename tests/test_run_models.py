"""Offline tests for code/run_models.py on an invented cohort with known answers."""

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import run_models as rm  # noqa: E402

COEF = {"eps_surprise_pct": 0.05, "log_market_cap": -0.4, "price_to_book": 0.02,
        "return_52w_pct": 0.01, "beta_252d": 0.8}


def invented_cohort(n=300, seed=1):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2026-04-20", periods=60)
    day0 = np.sort(rng.choice(days, n))
    frame = pd.DataFrame({
        "event_id": [f"SYN{i:03d}_2026-06-30" for i in range(n)],
        "ticker": [f"SYN{i:03d}" for i in range(n)],
        "day0_session": pd.DatetimeIndex(day0).strftime("%Y-%m-%d"),
        "earnings_timestamp": (pd.DatetimeIndex(day0) + pd.Timedelta(hours=7)
                               + pd.to_timedelta(np.arange(n) % 50, unit="s")
                               ).strftime("%Y-%m-%dT%H:%M:%S-04:00"),
        "primary_timing_sample": rng.random(n) > 0.1,
        "eps_surprise_pct": rng.normal(5, 10, n),
        "log_market_cap": rng.normal(24.5, 1, n),
        "price_to_book": rng.lognormal(1.3, 0.6, n),
        "return_52w_pct": rng.normal(15, 30, n),
        "beta_252d": rng.normal(0.8, 0.4, n),
    })
    signal = sum(frame[c] * b for c, b in COEF.items())
    frame["car_0_1_pct"] = 10 + signal + rng.normal(0, 0.01, n)
    return frame


class RunModelsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cohort = invented_cohort()
        self.path = self.root / "cohort.csv"
        self.cohort.to_csv(self.path, index=False)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_values_are_dropped_not_filled(self):
        self.cohort.loc[[0, 5], "price_to_book"] = np.nan
        self.cohort.to_csv(self.path, index=False)
        frame, flow = rm.load_sample(self.path, primary_only=False)
        self.assertEqual(len(frame), len(self.cohort) - 2)
        self.assertEqual(flow[-1]["n"], len(frame))
        self.assertNotIn(self.cohort.loc[0, "event_id"], set(frame["event_id"]))

    def test_split_keeps_each_day0_on_one_side(self):
        frame, _ = rm.load_sample(self.path, primary_only=False)
        train, test = rm.chronological_split(frame)
        self.assertFalse(set(train["day0"]) & set(test["day0"]))
        self.assertGreaterEqual(len(train), np.ceil(0.6 * len(frame)))
        self.assertLess(train["timestamp_utc"].max(), test["timestamp_utc"].min())

    def test_recovers_planted_coefficients_without_winsorizing(self):
        frame, _ = rm.load_sample(self.path, primary_only=False)
        result, _ = rm.fit(frame, bounds={})
        for column, beta in COEF.items():
            name = next(k for k, v in rm.RUN1.items() if v == column)
            self.assertAlmostEqual(result.params[name], beta, places=3)

    def test_winsorizing_uses_given_bounds(self):
        frame, _ = rm.load_sample(self.path, primary_only=False)
        x = rm.design(frame, {"price_to_book": (2.0, 3.0)})
        self.assertGreaterEqual(x["price_to_book"].min(), 2.0)
        self.assertLessEqual(x["price_to_book"].max(), 3.0)

    def test_main_writes_dashboard_contract_files(self):
        out = self.root / "out"
        rm.main(["--cohort", str(self.path), "--out-dir", str(out)])
        metrics = pd.read_csv(out / "model_comparison_metrics.csv")
        self.assertEqual(list(metrics["model"]), ["baseline", "baseline_all_events"])
        for column in ("model", "mae", "rmse", "out_of_sample_r2", "train_n", "test_n", "data_status"):
            self.assertIn(column, metrics.columns)
        self.assertTrue((metrics["data_status"] == "cohort").all())
        primary = metrics.iloc[0]
        self.assertGreater(primary["out_of_sample_r2"], 0.9)  # planted, low noise
        self.assertLess(primary["mse_gain_ci_low"], primary["mse_gain_ci_high"])
        holdout = pd.read_csv(out / "holdout_predictions.csv")
        self.assertEqual(len(holdout), primary["test_n"])
        self.assertTrue(holdout["language_model_prediction"].isna().all())
        flow = pd.read_csv(out / "run1_sample_flow.csv")
        self.assertEqual(flow[flow["sample"] == "primary"]["n"].iloc[-1],
                         primary["train_n"] + primary["test_n"])

    def test_bootstrap_is_deterministic(self):
        frame, _ = rm.load_sample(self.path, primary_only=False)
        _, test = rm.chronological_split(frame)
        gain = np.linspace(-1, 1, len(test))
        a, _ = rm.week_block_bootstrap(test, gain, draws=200)
        b, _ = rm.week_block_bootstrap(test, gain, draws=200)
        np.testing.assert_allclose(a, b)


if __name__ == "__main__":
    unittest.main()
