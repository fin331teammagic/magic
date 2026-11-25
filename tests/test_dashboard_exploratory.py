"""Tests for the dashboard's exploratory-screen reader and proposed lead rule."""

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))
import exploratory as ex  # noqa: E402


def row(model, variable, coef, q, dmse, placebo, handling="dropped"):
    return {"model": model, "variable": variable, "null_handling": handling, "coef": coef,
            "bh_q_within_model": q, "delta_mse": dmse, "placebo_share": placebo}


class ProposedLeadsTest(unittest.TestCase):
    def test_lead_needs_the_checks_to_replicate(self):
        single = pd.DataFrame([
            row("A", "good", 1.0, 0.01, 1.0, 0.01), row("B", "good", 0.5, 0.05, 0.5, 0.02),
            row("C", "good", 0.5, 0.50, -0.5, 0.60), row("consensus", "good", 0.8, 0.01, 0.9, 0.01),
            # Same sign everywhere, but only A passes: not a lead (the old sign-only rule passed it).
            row("A", "lucky", 1.0, 0.01, 1.0, 0.01), row("B", "lucky", 0.3, 0.60, -0.2, 0.70),
            row("C", "lucky", 0.2, 0.80, -0.1, 0.90),
            row("A", "flip", 1.0, 0.01, 1.0, 0.01), row("B", "flip", -1.0, 0.01, 1.0, 0.01),
            row("A", "noholdout", 1.0, 0.01, -1.0, 0.01), row("B", "noholdout", 1.0, 0.01, -1.0, 0.01),
            row("A", "good", 9.0, 0.0, 9.0, 0.0, handling="coded_0_plus_indicator"),
        ])
        leads = ex.proposed_leads(single).set_index(["model", "variable"])
        self.assertEqual(len(leads), 11)  # null-coded variant is not a lead candidate
        self.assertTrue(leads.loc[("A", "good"), "proposed_lead"])
        self.assertTrue(leads.loc[("B", "good"), "proposed_lead"])
        self.assertFalse(leads.loc[("C", "good"), "proposed_lead"])  # fails its own checks
        self.assertTrue(leads.loc[("consensus", "good"), "proposed_lead"])
        self.assertEqual(leads.loc[("A", "good"), "models_passing_same_sign"], 2)  # consensus not counted
        self.assertFalse(leads.loc[("A", "lucky"), "proposed_lead"])
        self.assertFalse(leads.loc[("A", "flip"), "proposed_lead"])  # passing models disagree in sign
        self.assertFalse(leads.loc[("A", "noholdout"), "proposed_lead"])  # holdout worse

    def test_row_against_the_majority_fails_direction(self):
        single = pd.DataFrame([row("A", "x", 1.0, 0.01, 1.0, 0.01), row("B", "x", -1.0, 0.01, 1.0, 0.01),
                               row("C", "x", -1.0, 0.01, 1.0, 0.01)])
        leads = ex.proposed_leads(single).set_index("model")
        self.assertFalse(leads.loc["A", "replicates"])
        self.assertTrue(leads.loc["B", "replicates"])
        self.assertEqual(leads.loc["A", "models_passing_same_sign"], 1)

    def test_one_model_never_passes_direction(self):
        single = pd.DataFrame([row("A", "x", 1.0, 0.001, 1.0, 0.0)])
        self.assertFalse(ex.proposed_leads(single)["proposed_lead"].any())

    def test_missing_q_is_not_a_pass(self):
        single = pd.DataFrame([row("A", "x", 1.0, np.nan, 1.0, 0.0), row("B", "x", 1.0, np.nan, 1.0, 0.0)])
        self.assertFalse(ex.proposed_leads(single)["survives_multiple_testing"].any())


class ScreenFilesTest(unittest.TestCase):
    def test_list_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(ex.list_screens(root / "absent"), [])
            (root / "incomplete").mkdir()
            (root / "s1").mkdir()
            pd.DataFrame([row("A", "x", 1, 0.1, 0, 0.5)]).to_csv(root / "s1" / "one_at_a_time.csv", index=False)
            (root / "s1" / "block.csv").write_text("")  # malformed file -> None, no crash
            self.assertEqual(ex.list_screens(root), ["s1"])
            frames = ex.load_screen("s1", root)
            self.assertEqual(len(frames["one_at_a_time"]), 1)
            self.assertIsNone(frames["block"])
            self.assertIsNone(frames["agreement"])

    def test_committed_screen_loads(self):
        screens = ex.list_screens()
        self.assertIn("v2.0_gemma4", screens)
        frames = ex.load_screen("v2.0_gemma4")
        self.assertTrue({"ci_low_per_sd", "ci_high_per_sd"} <= set(frames["one_at_a_time"].columns))


if __name__ == "__main__":
    unittest.main()
