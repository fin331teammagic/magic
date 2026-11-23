"""Describe the Run 2 and Run 3 predictors before the nested models are fit.

Answers two questions on the exact Run 1-3 common sample, without reading
any outcome value (the holdout stays untouched):

1. Does each LLM variable vary enough to explain anything?
2. Do the LLM variables just re-measure what Run 1-2 already measure (EPS
   surprise, dictionary sentiment)? This is the course lead's "don't use an
   LLM to measure a desk when you have a ruler" point.

Writes ``outputs/run3_feature_distribution.csv`` and
``outputs/run3_feature_correlations.csv`` (Spearman, primary sample).

    python code/describe_run3_features.py \
        --llm-scores outputs/llm_scores_real/q2_2026_llm_scores_v2.0_gemma4_after_cutoff395.csv
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_nested_models as nm  # noqa: E402

OUTCOME_COLUMNS = ("car_0_1_pct",)
REFERENCE = ["eps_surprise_pct", *nm.RUN2]


def describe(frame):
    """Value counts and spread for each Run 3 variable."""
    rows = []
    for name in nm.RUN3:
        values = frame[name]
        counts = values.value_counts().sort_index()
        rows.append(
            {
                "variable": name,
                "n": int(values.notna().sum()),
                "mean": round(values.mean(), 3),
                "sd": round(values.std(), 3),
                "modal_value": counts.idxmax(),
                "modal_share": round(counts.max() / counts.sum(), 3),
                **{f"count_{k}": int(counts.get(k, 0)) for k in (-1, 0, 1, 2)},
                "count_null": int(values.isna().sum()),
            }
        )
    return pd.DataFrame(rows)


def correlations(frame):
    """Spearman correlations of each Run 3 variable with Run 3, EPS surprise and Run 2."""
    columns = [*nm.RUN3, *REFERENCE]
    matrix = frame[columns].corr(method="spearman")
    return matrix.loc[list(nm.RUN3), columns].round(3)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--llm-scores", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=nm.DEFAULT_OUT)
    args = parser.parse_args(argv)

    frame, flow = nm.load_sample(
        nm.DEFAULT_COHORT, nm.DEFAULT_DICTIONARY, nm.DEFAULT_DAY0, args.llm_scores,
        primary_only=True,
    )
    frame = frame.drop(columns=[c for c in OUTCOME_COLUMNS if c in frame], errors="ignore")
    print(f"Primary common sample: {len(frame)} events")

    dist = describe(frame)
    corr = correlations(frame)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    dist.to_csv(args.out_dir / "run3_feature_distribution.csv", index=False)
    corr.to_csv(args.out_dir / "run3_feature_correlations.csv")
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(dist.to_string(index=False))
        print(corr.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
