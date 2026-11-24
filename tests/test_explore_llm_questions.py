"""Offline tests for code/explore_llm_questions.py on invented v3.0 scores."""

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import explore_llm_questions as ex  # noqa: E402
from test_run_nested_models import write_inputs  # noqa: E402

V3 = [name for name, (group, _, _) in ex.QUESTIONS.items() if group.startswith("v3.0")]
GROUPS = {g: [n for n in V3 if ex.QUESTIONS[n][0] == g] for g in ("v3.0-A", "v3.0-B", "v3.0-C", "v3.0-D")}
PLANTED = "pricing_power"  # nullable, group B


def invented_scores(ids, seed):
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame({"id": ids})
    for name in V3:
        allowed = sorted(ex.QUESTIONS[name][1])
        frame[name] = rng.choice(allowed, len(ids)).astype(float)
        if ex.QUESTIONS[name][2]:
            frame.loc[rng.random(len(ids)) < 0.15, name] = np.nan
    frame["status"] = "scored"
    frame["parse_status"] = "ok"
    return frame


def write_csv(frame, path):
    frame.to_csv(path, index=False, na_rep="null")
    return path


class ExploreLlmQuestionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write_inputs(self.root, n=300, seed=4)
        cohort = pd.read_csv(self.root / "cohort.csv")
        ids = cohort["event_id"]
        self.a = invented_scores(ids, seed=10)
        self.b = invented_scores(ids, seed=11)
        cohort["car_0_1_pct"] += 4 * self.a[PLANTED].fillna(0)
        cohort.to_csv(self.root / "cohort.csv", index=False)
        # Model A comes in four prompt-group files; group B failed for one call.
        self.a_files = []
        for group, names in GROUPS.items():
            part = self.a[["id", *names, "status", "parse_status"]].copy()
            if group == "v3.0-B":
                part.loc[6, "parse_status"] = "error"
                part.loc[6, names] = np.nan
            self.a_files.append(write_csv(part, self.root / f"a_{group}.csv"))
        self.b_file = write_csv(self.b, self.root / "b.csv")
        self.failed_id = ids[6]

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *extra):
        out = self.root / "out"
        ex.main(["--scores", "A=" + ",".join(map(str, self.a_files)),
                 "--scores", f"B={self.b_file}", "--scores", f"C={self.b_file}",
                 "--cohort", str(self.root / "cohort.csv"),
                 "--dictionary-features", str(self.root / "text.csv"),
                 "--day0-check", str(self.root / "day0.csv"),
                 "--placebo-draws", "50", "--out-dir", str(out), *extra])
        return {name: pd.read_csv(out / f"{name}.csv")
                for name in ("distribution", "agreement", "one_at_a_time", "block", "overlap")}

    def test_group_files_join_and_failed_group_is_not_a_null(self):
        frame, valid, _ = ex.load_model(self.a_files)
        self.assertEqual(set(frame.columns) - {"event_id"}, set(V3))
        self.assertNotIn(self.failed_id, valid[PLANTED])
        self.assertIn(self.failed_id, valid["outlook_vs_quarter"])

    def test_file_report_records_scoring_details(self):
        _, _, report = ex.load_model(self.a_files)
        group_b = next(r for r in report if "pricing_power" in r["variables"])
        self.assertEqual(group_b["parse_errors"], 1)
        self.assertEqual(group_b["parse_error_ids"], self.failed_id)
        self.assertEqual(group_b["rows"], 300)
        self.assertEqual(group_b["valid_rows"], 299)

    def test_clustered_wald_withheld_with_too_few_clusters(self):
        rng = np.random.default_rng(3)
        n = 120
        frame = pd.DataFrame({c: rng.normal(size=n) for c in ["x1", "x2", "a", "b", "c", "d"]})
        frame["car_0_1_pct"] = rng.normal(size=n)
        frame["eps_surprise_pct"] = frame["price_to_book"] = rng.normal(size=n)  # winsorized columns
        frame["day0"] = pd.to_datetime("2026-07-01") + pd.to_timedelta(np.arange(n) % 4, unit="D")
        out = ex.incremental(frame, ["x1", "x2"], ["a", "b", "c", "d"],
                             frame["day0"] <= "2026-07-02", placebo_draws=0)
        self.assertTrue(np.isnan(out["block_wald_p"]))
        self.assertIn("4 day-0 clusters", out["block_wald_note"])
        self.assertTrue(0 <= out["block_f_p_unclustered"] <= 1)

    def test_value_outside_rubric_is_rejected(self):
        bad = self.b.copy()
        bad.loc[0, "ai_emphasis"] = 3
        with self.assertRaisesRegex(ValueError, "ai_emphasis"):
            ex.read_score_file(write_csv(bad, self.root / "bad.csv"))

    def test_null_on_non_nullable_question_is_rejected(self):
        bad = self.b.copy()
        bad.loc[0, "capex_change"] = np.nan
        with self.assertRaisesRegex(ValueError, "no null option"):
            ex.read_score_file(write_csv(bad, self.root / "bad.csv"))

    def test_variable_in_two_files_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "appears in both"):
            ex.load_model([self.b_file, self.a_files[0]])

    def test_benjamini_hochberg(self):
        q = ex.benjamini_hochberg([0.01, 0.04, np.nan, 0.03, 0.5])
        np.testing.assert_allclose(q[[0, 1, 3, 4]], [0.04, 0.0533333, 0.0533333, 0.5], rtol=1e-5)
        self.assertTrue(np.isnan(q[2]))

    def test_end_to_end(self):
        out = self.run_main()
        single = out["one_at_a_time"]
        dropped = single[single["null_handling"] == "dropped"]
        # The planted question is the top hit for model A and the consensus.
        for model in ("A", "consensus"):
            rows = dropped[dropped["model"] == model].sort_values("p_value")
            self.assertEqual(rows.iloc[0]["variable"], PLANTED)
            self.assertLess(rows.iloc[0]["bh_q_within_model"], 0.01)
            self.assertGreater(rows.iloc[0]["delta_mse"], 0)
        # Nulls are dropped, not zero-filled; the coded variant keeps them.
        planted = single[(single["model"] == "A") & (single["variable"] == PLANTED)].set_index("null_handling")
        self.assertLess(planted.loc["dropped", "n"], planted.loc["coded_0_plus_indicator", "n"])
        # B and C are the same file: perfect agreement; A vs B is chance-level.
        agree = out["agreement"]
        same = agree[(agree["model_a"] == "B") & (agree["model_b"] == "C")]
        self.assertTrue(np.allclose(same["exact_agreement"], 1))
        self.assertTrue(np.allclose(same["weighted_kappa"].dropna(), 1))
        self.assertLess(agree[(agree["model_a"] == "A") & (agree["model_b"] == "B")]["weighted_kappa"].abs().max(), 0.3)
        self.assertEqual(set(out["distribution"]["model"]), {"A", "B", "C", "consensus"})
        # The block excludes the call whose group B prompt failed.
        block = out["block"].set_index("model")
        self.assertEqual(block.loc["A", "n_questions"], 20)
        self.assertLess(block.loc["A", "n"], block.loc["B", "n"])
        # More restrictions than day-0 clusters: the clustered Wald p is withheld, not reported.
        if block.loc["A", "n_added_columns"] >= block.loc["A", "n_clusters"] - 1:
            self.assertTrue(np.isnan(block.loc["A", "block_wald_p"]))
            self.assertIn("undefined", block.loc["A", "block_wald_note"])
        self.assertTrue(block["block_f_p_unclustered"].between(0, 1).all())
        self.assertTrue((out["one_at_a_time"]["status"] == "EXPLORATORY (not pre-specified)").all())

    def test_run3_baseline_needs_reference(self):
        with self.assertRaises(SystemExit):
            self.run_main("--baseline", "run3")

    def test_run3_baseline(self):
        rng = np.random.default_rng(12)
        ids = pd.read_csv(self.root / "cohort.csv")["event_id"]
        v2 = pd.DataFrame({"id": ids, "status": "scored", "parse_status": "ok",
                           **{n: rng.choice(sorted(ex.QUESTIONS[n][1]), len(ids)).astype(float)
                              for n in ex.nm.RUN3}})
        reference = write_csv(v2, self.root / "v2.csv")
        out = self.run_main("--baseline", "run3", "--reference-llm", str(reference))
        self.assertTrue((out["one_at_a_time"]["baseline"] == "run3").all())
        self.assertIn("rho_v2_guidance_revision", out["overlap"].columns)


if __name__ == "__main__":
    unittest.main()
