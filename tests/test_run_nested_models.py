"""Offline tests for code/run_nested_models.py with a planted Run 3 effect."""

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_nested_models as nm  # noqa: E402
from test_run_models import invented_cohort  # noqa: E402


def write_inputs(root, n=300, seed=2):
    rng = np.random.default_rng(seed)
    cohort = invented_cohort(n=n, seed=seed)
    ids = cohort["event_id"]
    text = pd.DataFrame({"event_id": ids, "after_training_cutoff": True,
                         **{c: rng.normal(0, 1, n) for c in nm.RUN2}})
    text.loc[0, "after_training_cutoff"] = False  # pre-cutoff call is dropped
    day0 = pd.DataFrame({"event_id": ids, "day0_check": "consistent_with_call"})
    day0.loc[1, "day0_check"] = "day0_precedes_call"  # mismatched day 0 is dropped
    llm = pd.DataFrame({"id": ids, **{c: rng.integers(-1, 3, n).astype(float) for c in nm.RUN3},
                        "status": "scored", "parse_status": "ok"})
    llm.loc[2, "parse_status"] = "error"  # unparsed score is dropped
    llm.loc[3, "guidance_revision"] = np.nan  # null score is dropped, not zero-filled
    # Plant a strong Run 3 effect on the outcome; Run 2 block is pure noise.
    cohort["car_0_1_pct"] = cohort["car_0_1_pct"] + 3 * llm["qa_evasiveness"].fillna(0)
    cohort.to_csv(root / "cohort.csv", index=False)
    text.to_csv(root / "text.csv", index=False)
    day0.to_csv(root / "day0.csv", index=False)
    llm.to_csv(root / "llm.csv", index=False)


class RunNestedModelsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write_inputs(self.root)
        self.paths = tuple(self.root / f for f in ("cohort.csv", "text.csv", "day0.csv", "llm.csv"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_sample_filters(self):
        frame, flow = nm.load_sample(*self.paths, primary_only=False)
        dropped = {"SYN000_2026-06-30", "SYN001_2026-06-30", "SYN002_2026-06-30", "SYN003_2026-06-30"}
        self.assertFalse(dropped & set(frame["event_id"]))
        self.assertEqual(len(frame), 296)
        self.assertEqual(flow[-1]["n"], len(frame))

    def test_null_category_keeps_null_rows_with_an_indicator(self):
        frame, _ = nm.load_sample(*self.paths, primary_only=False, null_category=True)
        self.assertEqual(len(frame), 297)  # SYN003 (null guidance) is kept
        row = frame.set_index("event_id").loc["SYN003_2026-06-30"]
        self.assertEqual(row["guidance_revision"], 0)
        self.assertEqual(row[nm.NULL_INDICATOR], 1)
        _, coefs, _, _ = nm.run_sample(self.paths, primary_only=False, placebo_draws=5,
                                       null_category=True, sample="x")
        self.assertIn(nm.NULL_INDICATOR, {c["variable"] for c in coefs if c["run"] == 3})
        self.assertNotIn(nm.NULL_INDICATOR, {c["variable"] for c in coefs if c["run"] == 2})

    def test_no_cutoff_filter_keeps_pre_cutoff_calls(self):
        frame, _ = nm.load_sample(*self.paths, primary_only=False, cutoff_filter=False)
        self.assertIn("SYN000_2026-06-30", set(frame["event_id"]))
        self.assertEqual(len(frame), 297)

    def test_planted_run3_effect_is_detected_and_run2_noise_is_not(self):
        runs, coefs, preds, _ = nm.run_sample(self.paths, primary_only=False, placebo_draws=50)
        by_run = {r["run"]: r for r in runs}
        self.assertTrue(by_run[3]["supported"])
        self.assertLess(by_run[3]["block_wald_p"], 0.001)
        self.assertLess(by_run[3]["placebo_share_at_least_actual"], 0.05)
        self.assertGreater(by_run[3]["out_of_sample_r2"], by_run[2]["out_of_sample_r2"])
        self.assertFalse(by_run[2]["supported"])
        self.assertEqual(len({(r["train_n"], r["test_n"]) for r in runs}), 1)  # same events
        self.assertEqual(len(preds), by_run[1]["test_n"])

    def test_main_writes_dashboard_layout(self):
        out = self.root / "out"
        nm.main(["--cohort", str(self.paths[0]), "--dictionary-features", str(self.paths[1]),
                 "--day0-check", str(self.paths[2]), "--llm-scores", str(self.paths[3]),
                 "--out-dir", str(out), "--data-status", "synthetic", "--placebo-draws", "20"])
        runs = pd.read_csv(out / "model_runs.csv")
        for column in ("run", "label", "out_of_sample_r2", "mae", "rmse", "train_n", "test_n",
                       "excluded_n", "data_status"):
            self.assertIn(column, runs.columns)
        coefs = pd.read_csv(out / "model_coefficients.csv")
        for column in ("run", "variable", "coef_per_sd", "ci_low", "ci_high", "data_status"):
            self.assertIn(column, coefs.columns)
        preds = pd.read_csv(out / "run_predictions.csv")
        for column in ("event_id", "actual", "pred_run1", "pred_run3", "data_status"):
            self.assertIn(column, preds.columns)


if __name__ == "__main__":
    unittest.main()
