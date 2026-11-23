"""Run 1 (fundamentals) on the real Q2 2026 cohort, as pre-specified.

Implements ``specs_tried.md`` sections 2-5 for Run 1 only:

- Sample: ``outputs/q2_2026_cohort.csv``, ``primary_timing_sample == True``
  (robustness: all events), complete cases on CAR[0,1] and the five Run 1
  variables. Missing values are dropped, never filled.
- Winsorizing (amendment 1): ``eps_surprise_pct`` and ``price_to_book`` at the
  1st and 99th percentiles of the estimation sample (the training set for
  the holdout).
- In-sample: OLS with an intercept; standard errors clustered by
  ``day0_session``; clustered Wald test that all five slopes are zero.
- Holdout: sort by ``earnings_timestamp`` (UTC); the first 60% of events
  train, moved forward to the end of a day-0 date so no date is in both
  sets; fit on training only; evaluate the holdout once.
- Supplementary (not pre-specified for Run 1): week-block bootstrap
  (2,000 draws, seed 331) of the MSE gain over the training-mean forecast.

Writes, in ``outputs/``:

- ``model_comparison_metrics.csv``: holdout metrics (model ``baseline`` =
  Run 1 on the primary sample; ``baseline_all_events`` = robustness).
- ``holdout_predictions.csv``: one row per primary holdout event.
- ``run1_coefficients.csv``: in-sample and training-set coefficients.
- ``run1_sample_flow.csv``: event counts at each filter step.

Run from the repository root:

    python code/run_models.py
"""

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

DEFAULT_COHORT = Path("outputs/q2_2026_cohort.csv")
DEFAULT_OUT = Path("outputs")
OUTCOME = "car_0_1_pct"
# specs_tried.md section 4 name -> cohort column (amendment 1).
RUN1 = {
    "eps_surprise_pct": "eps_surprise_pct",
    "log_market_cap": "log_market_cap",
    "price_to_book": "price_to_book",
    "price_change_52w_pct": "return_52w_pct",
    "beta": "beta_252d",
}
WINSORIZE = ["eps_surprise_pct", "price_to_book"]
WINSOR_LIMITS = (0.01, 0.99)
TRAIN_SHARE = 0.60
BOOTSTRAP_DRAWS = 2000
SEED = 331
MIN_EVENTS = 50
DATA_STATUS = "cohort"
LABEL = "Run 1: fundamentals"


def load_sample(path, primary_only):
    """Return (complete-case frame, sample-flow rows)."""
    cohort = pd.read_csv(path)
    if cohort["event_id"].duplicated().any():
        raise ValueError("event_id is not unique in the cohort file.")
    sample_name = "primary" if primary_only else "all_events"
    flow = [{"sample": sample_name, "step": "cohort events", "n": len(cohort)}]
    frame = cohort
    if primary_only:
        frame = frame[frame["primary_timing_sample"] == True]  # noqa: E712
        flow.append({"sample": sample_name, "step": "primary_timing_sample == True",
                     "n": len(frame)})
    for column in [OUTCOME] + list(RUN1.values()):
        frame = frame[frame[column].notna()]
        flow.append({"sample": sample_name, "step": f"{column} present", "n": len(frame)})
    frame = frame.copy()
    frame["timestamp_utc"] = pd.to_datetime(frame["earnings_timestamp"], utc=True)
    frame["day0"] = pd.to_datetime(frame["day0_session"])
    if frame["day0"].isna().any() or frame["timestamp_utc"].isna().any():
        raise ValueError("Complete-case events must have a timestamp and day 0.")
    frame = frame.sort_values(["timestamp_utc", "event_id"]).reset_index(drop=True)
    return frame, flow


def winsor_bounds(frame):
    return {
        name: tuple(frame[RUN1[name]].quantile(list(WINSOR_LIMITS)))
        for name in WINSORIZE
    }


def design(frame, bounds):
    """Predictor matrix (spec names) with winsorizing from the given bounds."""
    x = pd.DataFrame({name: frame[column].astype(float) for name, column in RUN1.items()})
    for name, (low, high) in bounds.items():
        x[name] = x[name].clip(low, high)
    return sm.add_constant(x, has_constant="add")


def fit(frame, bounds):
    x = design(frame, bounds)
    y = frame[OUTCOME].astype(float)
    groups = frame["day0"].factorize()[0]
    return sm.OLS(y, x).fit(cov_type="cluster", cov_kwds={"groups": groups}), x


def chronological_split(frame):
    """First 60% by timestamp, moved forward to the end of a day-0 date."""
    n_train = int(np.ceil(TRAIN_SHARE * len(frame)))
    boundary_day = frame.loc[n_train - 1, "day0"]
    train = frame[frame["day0"] <= boundary_day]
    test = frame[frame["day0"] > boundary_day]
    if set(train["day0"]) & set(test["day0"]):
        raise ValueError("A day-0 date appears in both training and holdout.")
    if len(train) + len(test) != len(frame):
        raise ValueError("Day 0 is not ordered with the timestamp; split is ambiguous.")
    return train, test


def week_block_bootstrap(test, loss_gain, draws=BOOTSTRAP_DRAWS, seed=SEED):
    """95% interval of mean(loss_gain) resampling Monday-Sunday weeks of day 0."""
    weeks = test["day0"].dt.to_period("W-SUN").to_numpy()
    blocks = [loss_gain[weeks == week] for week in pd.unique(weeks)]
    rng = np.random.default_rng(seed)
    stats = np.empty(draws)
    for i in range(draws):
        pick = rng.integers(0, len(blocks), len(blocks))
        sample = np.concatenate([blocks[j] for j in pick])
        stats[i] = sample.mean()
    return np.percentile(stats, [2.5, 97.5]), len(blocks)


def coefficient_rows(result, x, sample, fit_on):
    sd = x.drop(columns="const").std(ddof=1)
    ci = result.conf_int()
    rows = []
    for name in result.params.index:
        scale = 1.0 if name == "const" else sd[name]
        rows.append({
            "sample": sample, "fit_on": fit_on, "run": 1, "variable": name,
            "coef": result.params[name], "clustered_se": result.bse[name],
            "t": result.tvalues[name], "p_value": result.pvalues[name],
            "ci_low": ci.loc[name, 0], "ci_high": ci.loc[name, 1],
            "coef_per_sd": result.params[name] * scale,
            "ci_low_per_sd": ci.loc[name, 0] * scale, "ci_high_per_sd": ci.loc[name, 1] * scale,
        })
    return rows


def run_sample(cohort_path, primary_only, provenance):
    frame, flow = load_sample(cohort_path, primary_only)
    sample = "primary" if primary_only else "all_events"
    if len(frame) < MIN_EVENTS:
        raise ValueError(f"Only {len(frame)} complete events; below the {MIN_EVENTS} minimum.")

    # In-sample on the full complete-case sample.
    full, x_full = fit(frame, winsor_bounds(frame))
    slopes = [name for name in RUN1]
    wald = full.f_test(np.eye(len(full.params))[1:])
    coefs = coefficient_rows(full, x_full, sample, "full_sample")

    # Chronological holdout, evaluated once.
    train, test = chronological_split(frame)
    bounds = winsor_bounds(train)
    train_fit, x_train = fit(train, bounds)
    coefs += coefficient_rows(train_fit, x_train, sample, "training_set")
    pred = train_fit.predict(design(test, bounds))
    actual = test[OUTCOME].to_numpy(dtype=float)
    err = actual - pred.to_numpy()
    mean_err = actual - train[OUTCOME].mean()
    gain = mean_err ** 2 - err ** 2  # per-event MSE gain over the training mean
    interval, n_weeks = week_block_bootstrap(test, gain)

    metrics = {
        "model": "baseline" if primary_only else "baseline_all_events",
        "run": 1, "label": LABEL, "sample": sample,
        "mae": np.mean(np.abs(err)),
        "rmse": np.sqrt(np.mean(err ** 2)),
        "out_of_sample_r2": 1 - np.sum(err ** 2) / np.sum(mean_err ** 2),
        "mse_gain_vs_train_mean": gain.mean(),
        "mse_gain_ci_low": interval[0], "mse_gain_ci_high": interval[1],
        "bootstrap_weeks": n_weeks,
        "train_n": len(train), "test_n": len(test),
        "excluded_n": flow[0]["n"] - len(frame),
        "train_cutoff": train["timestamp_utc"].max().isoformat(),
        "test_start": test["timestamp_utc"].min().isoformat(),
        "last_train_day0": train["day0"].max().date().isoformat(),
        "first_test_day0": test["day0"].min().date().isoformat(),
        "in_sample_n": int(full.nobs), "in_sample_clusters": len(frame["day0"].unique()),
        "in_sample_r2": full.rsquared, "in_sample_adj_r2": full.rsquared_adj,
        "in_sample_wald_f": float(np.squeeze(wald.fvalue)), "in_sample_wald_p": float(wald.pvalue),
        "outcome": OUTCOME,
        "baseline_features": ";".join(slopes),
        "language_features": "",
        "winsorized": ";".join(f"{k}[{lo:.4g},{hi:.4g}]" for k, (lo, hi) in bounds.items()),
        **provenance,
        "data_status": DATA_STATUS,
    }
    predictions = pd.DataFrame({
        "event_id": test["event_id"].to_numpy(),
        "ticker": test["ticker"].to_numpy(),
        "earnings_timestamp": test["earnings_timestamp"].to_numpy(),
        "day0_session": test["day0_session"].to_numpy(),
        "actual": actual,
        "baseline_prediction": pred.to_numpy(),
        "language_model_prediction": np.nan,  # Runs 2-3 not yet run
        "data_status": DATA_STATUS,
    })
    return metrics, predictions, coefs, flow


def provenance_fields(cohort_path):
    def git(*args):
        try:
            return subprocess.run(["git", *args], capture_output=True, text=True,
                                  check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return ""
    return {
        "cohort_file": str(cohort_path),
        "cohort_file_commit": git("log", "-1", "--format=%h", "--", str(cohort_path)),
        "code_commit": git("rev-parse", "--short", "HEAD"),
        "run_date": date.today().isoformat(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cohort", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    provenance = provenance_fields(args.cohort)
    metrics, coefs, flows, holdout = [], [], [], None
    for primary_only in (True, False):
        m, p, c, f = run_sample(args.cohort, primary_only, provenance)
        metrics.append(m)
        coefs += c
        flows += f
        if primary_only:
            holdout = p

    args.out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(metrics).to_csv(args.out_dir / "model_comparison_metrics.csv", index=False)
    holdout.to_csv(args.out_dir / "holdout_predictions.csv", index=False)
    coef_frame = pd.DataFrame(coefs)
    coef_frame["data_status"] = DATA_STATUS
    coef_frame.to_csv(args.out_dir / "run1_coefficients.csv", index=False)
    pd.DataFrame(flows).to_csv(args.out_dir / "run1_sample_flow.csv", index=False)

    for m in metrics:
        print(f"[{m['sample']}] in-sample n={m['in_sample_n']} R2={m['in_sample_r2']:.4f} "
              f"adjR2={m['in_sample_adj_r2']:.4f} Wald p={m['in_sample_wald_p']:.4f} | "
              f"holdout train/test={m['train_n']}/{m['test_n']} OOS R2={m['out_of_sample_r2']:.4f} "
              f"RMSE={m['rmse']:.3f} MAE={m['mae']:.3f} "
              f"MSE gain 95% CI [{m['mse_gain_ci_low']:.3f}, {m['mse_gain_ci_high']:.3f}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
