"""EXPLORATORY (not pre-specified): the management-minus-analyst sentiment gap.

Amendment 5 keeps the gap out of the official runs, because Run 2 already
contains both of its inputs. This script reports it afterwards, on the same
304-event primary sample, as Cammy asked:

- Spearman correlation of the gap with CAR[0,1];
- in-sample OLS of CAR[0,1] on the Run 1 variables plus the gap, with
  day-0-clustered standard errors.

No holdout is used. Writes ``outputs/exploratory_sentiment_gap.csv``.

    python code/exploratory_sentiment_gap.py \\
        --llm-scores outputs/llm_scores_real/q2_2026_llm_scores_v2.0_gemma4_after_cutoff395.csv
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_models as rm  # noqa: E402
import run_nested_models as nm  # noqa: E402

GAP = "sentiment_gap"


def add_gap(frame):
    frame = frame.copy()
    frame[GAP] = frame["management_prepared_sentiment"] - frame["analyst_question_sentiment"]
    return frame


def analyze(frame):
    frame = add_gap(frame)
    rho = frame[[GAP, rm.OUTCOME]].corr(method="spearman").iloc[0, 1]
    model, x = nm.fit(frame, list(rm.RUN1) + [GAP], nm.bounds_for(frame))
    sd = frame[GAP].std(ddof=1)
    return {
        "label": "EXPLORATORY, not pre-specified (Amendment 5)",
        "n": int(model.nobs),
        "gap_mean": frame[GAP].mean(), "gap_sd": sd,
        "spearman_with_car_0_1": rho,
        "coef_per_sd_controlling_run1": model.params[GAP] * sd,
        "ci_low_per_sd": model.conf_int().loc[GAP, 0] * sd,
        "ci_high_per_sd": model.conf_int().loc[GAP, 1] * sd,
        "p_value_clustered": model.pvalues[GAP],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--llm-scores", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("outputs/exploratory_sentiment_gap.csv"))
    args = parser.parse_args(argv)
    frame, _ = nm.load_sample(nm.DEFAULT_COHORT, nm.DEFAULT_DICTIONARY, nm.DEFAULT_DAY0,
                              args.llm_scores, primary_only=True)
    result = analyze(frame)
    pd.DataFrame([result]).to_csv(args.out, index=False)
    for key, value in result.items():
        print(f"{key}: {value:.4f}" if isinstance(value, float) else f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
