"""Reliability check: agreement between two LLM scoring runs of the same calls.

Prof. Bowen's run notes that the Run 3 scores come from one temperature-0
run, with no repeat or second-model check on real calls. This script
compares a second run (same model with a new seed, or another model) with the
original on the calls both scored:

- exact agreement for each variable;
- Cohen's kappa, quadratic-weighted (the scales are ordered), with nulls
  counted as agreement only when both runs are null;
- status agreement.

Writes nothing but the CSV given by ``--out`` (numbers only).

    python code/compare_llm_runs.py \\
        --first outputs/llm_scores_real/q2_2026_llm_scores_v2.0_gemma4_all474.csv \\
        --second <second run CSV> --out outputs/llm_reliability.csv

``--make-sample N`` instead writes ``inputs/llm_reliability_sample_ids.csv``:
N event IDs drawn with seed 331 from the Run 1-3 primary sample, for the
second run to score.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
RUN3 = ["guidance_specificity", "guidance_revision", "qa_evasiveness",
        "one_off_attribution", "analyst_concern_focus"]
SEED = 331


def weighted_kappa(a, b):
    """Quadratic-weighted Cohen's kappa for two integer ratings."""
    a, b = np.asarray(a, dtype=int), np.asarray(b, dtype=int)
    levels = np.union1d(a, b)
    if len(levels) < 2:
        return np.nan
    index = {v: i for i, v in enumerate(levels)}
    k = len(levels)
    observed = np.zeros((k, k))
    for x, y in zip(a, b):
        observed[index[x], index[y]] += 1
    observed /= observed.sum()
    expected = np.outer(observed.sum(axis=1), observed.sum(axis=0))
    weights = np.array([[(i - j) ** 2 for j in range(k)] for i in range(k)]) / (k - 1) ** 2
    denominator = (weights * expected).sum()
    return np.nan if denominator == 0 else 1 - (weights * observed).sum() / denominator


def compare(first, second):
    ok = lambda f: f[f["parse_status"] == "ok"].set_index("id")  # noqa: E731
    joined = ok(first).join(ok(second), how="inner", lsuffix="_1", rsuffix="_2")
    rows = []
    for name in RUN3:
        x, y = joined[f"{name}_1"], joined[f"{name}_2"]
        both = x.notna() & y.notna()
        rows.append({
            "variable": name, "n_calls": len(joined),
            "exact_agreement": float(((x == y) | (x.isna() & y.isna())).mean()),
            "weighted_kappa": weighted_kappa(x[both], y[both]) if both.sum() else np.nan,
            "null_in_one_run_only": int((x.isna() ^ y.isna()).sum()),
        })
    rows.append({"variable": "status", "n_calls": len(joined),
                 "exact_agreement": float((joined["status_1"] == joined["status_2"]).mean()),
                 "weighted_kappa": np.nan, "null_in_one_run_only": 0})
    return pd.DataFrame(rows)


def make_sample(n, out):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import run_nested_models as nm
    llm = Path("outputs/llm_scores_real/q2_2026_llm_scores_v2.0_gemma4_after_cutoff395.csv")
    frame, _ = nm.load_sample(nm.DEFAULT_COHORT, nm.DEFAULT_DICTIONARY, nm.DEFAULT_DAY0, llm, primary_only=True)
    ids = frame["event_id"].sample(n=n, random_state=SEED).sort_values()
    pd.DataFrame({"event_id": ids}).to_csv(out, index=False)
    print(f"Wrote {n} event IDs (seed {SEED}, from {len(frame)} primary events) to {out}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--first", type=Path)
    parser.add_argument("--second", type=Path)
    parser.add_argument("--out", type=Path, default=Path("outputs/llm_reliability.csv"))
    parser.add_argument("--make-sample", type=int)
    args = parser.parse_args(argv)
    if args.make_sample:
        make_sample(args.make_sample, Path("inputs/llm_reliability_sample_ids.csv"))
        return 0
    result = compare(pd.read_csv(args.first), pd.read_csv(args.second))
    result.to_csv(args.out, index=False)
    print(result.round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
