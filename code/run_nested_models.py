"""Nested Runs 1-3 on the real cohort, as pre-specified (not yet run).

Implements ``specs_tried.md`` sections 2-5 with Amendments 1-3 once real LLM
scores exist:

- Sample: cohort events (primary, or all events for robustness) whose call
  was held after the 2026-06-30 training cutoff, whose day 0 matches the call
  (``outputs/q2_2026_day0_transcript_check.csv``), and that have the outcome
  and all 15 Run 1-3 variables. LLM rows count only if they parsed and have
  ``status == "scored"``. Missing values are dropped, never filled.
- Runs: OLS with an intercept on the same events. Run 1 = fundamentals,
  Run 2 = + dictionary text, Run 3 = + LLM variables. Winsorizing as in
  Amendment 1.
- In-sample: R2, adjusted R2, and a day-0-clustered Wald test that the added
  block is jointly zero.
- Holdout (once): 60/40 chronological split at a day-0 boundary; OOS R2, MAE
  and RMSE; dMSE = MSE(previous) - MSE(this) for Runs 2 vs 1 and 3 vs 2, with
  the week-block bootstrap (2,000 draws, seed 331) and the shuffled-score
  placebo (1,000 draws, seed 331). "Supported" only if the bootstrap 95%
  interval lies entirely above zero.

Robustness variants (Amendment 5), each labeled in the ``sample`` column:

- ``all_events``: no primary-timing filter.
- ``primary_null_category``: ``guidance_revision = null`` coded 0 plus a
  ``no_prior_guidance`` indicator in the Run 3 block, instead of dropped.
- ``primary_all_calls``: no training-cutoff filter (needs ``--llm-scores-all``
  with all 474 calls scored).

Writes ``outputs/model_runs.csv``, ``outputs/model_coefficients.csv``,
``outputs/run_predictions.csv`` and ``outputs/nested_sample_flow.csv``, in the
dashboard's three-run layout.

    python code/run_nested_models.py --llm-scores restricted_data/llm_outputs/q2_2026_sonnet_scores.csv
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_models as rm  # noqa: E402

DEFAULT_COHORT = Path("outputs/q2_2026_cohort.csv")
DEFAULT_DICTIONARY = Path("outputs/q2_2026_dictionary_features.csv")
DEFAULT_DAY0 = Path("outputs/q2_2026_day0_transcript_check.csv")
DEFAULT_OUT = Path("outputs")
RUN2 = ["transcript_sentiment", "management_prepared_sentiment",
        "analyst_question_sentiment", "uncertainty_word_proportion",
        "congratulations_mentioned"]
RUN3 = ["guidance_specificity", "guidance_revision", "qa_evasiveness",
        "one_off_attribution", "analyst_concern_focus"]
NULL_INDICATOR = "no_prior_guidance"


def make_blocks(run3=RUN3):
    """Predictor lists for Runs 1-3 and the block each run adds."""
    blocks = {1: list(rm.RUN1), 2: list(rm.RUN1) + RUN2, 3: list(rm.RUN1) + RUN2 + list(run3)}
    return blocks, {2: RUN2, 3: list(run3)}


BLOCKS, ADDED = make_blocks()
VARIANTS = {
    "primary": {"primary_only": True},
    "all_events": {"primary_only": False},
    "primary_null_category": {"primary_only": True, "null_category": True},
    "primary_all_calls": {"primary_only": True, "cutoff_filter": False},
}
LABELS = {1: "Run 1: fundamentals", 2: "Run 2: + dictionary text",
          3: "Run 3: + LLM variables"}
PLACEBO_DRAWS = 1000


def load_sample(cohort_path, dictionary_path, day0_path, llm_path, primary_only,
                null_category=False, cutoff_filter=True, sample=None):
    cohort = pd.read_csv(cohort_path)
    for name, column in rm.RUN1.items():
        cohort[name] = cohort[column]
    text = pd.read_csv(dictionary_path)[["event_id", "after_training_cutoff"] + RUN2]
    day0 = pd.read_csv(day0_path)[["event_id", "day0_check"]]
    llm = pd.read_csv(llm_path)
    llm = llm[(llm["parse_status"] == "ok") & (llm["status"] == "scored")]
    llm = llm.rename(columns={"id": "event_id"})[["event_id"] + RUN3]
    run3 = list(RUN3)
    if null_category:
        llm[NULL_INDICATOR] = llm["guidance_revision"].isna().astype(float)
        llm["guidance_revision"] = llm["guidance_revision"].fillna(0)
        run3.append(NULL_INDICATOR)
    frame = (cohort.merge(text, on="event_id", how="left", validate="one_to_one")
             .merge(day0, on="event_id", how="left", validate="one_to_one")
             .merge(llm, on="event_id", how="left", validate="one_to_one"))
    sample = sample or ("primary" if primary_only else "all_events")
    flow = [{"sample": sample, "step": "cohort events", "n": len(frame)}]

    def keep(mask, step):
        nonlocal frame
        frame = frame[mask]
        flow.append({"sample": sample, "step": step, "n": len(frame)})

    if primary_only:
        keep(frame["primary_timing_sample"] == True, "primary_timing_sample == True")  # noqa: E712
    if cutoff_filter:
        keep(frame["after_training_cutoff"] == True, "call after 2026-06-30 cutoff")  # noqa: E712
    else:
        keep(frame["after_training_cutoff"].notna(), "call matched (any date)")
    keep(frame["day0_check"] == "consistent_with_call", "day 0 consistent with call")
    for column in [rm.OUTCOME] + make_blocks(run3)[0][3]:
        keep(frame[column].notna(), f"{column} present")
    frame = frame.copy()
    frame["timestamp_utc"] = pd.to_datetime(frame["earnings_timestamp"], utc=True)
    frame["day0"] = pd.to_datetime(frame["day0_session"])
    frame = frame.sort_values(["timestamp_utc", "event_id"]).reset_index(drop=True)
    return frame, flow


def bounds_for(frame):
    return {name: tuple(frame[name].quantile(list(rm.WINSOR_LIMITS))) for name in rm.WINSORIZE}


def design(frame, columns, bounds):
    x = frame[columns].astype(float).copy()
    for name, (low, high) in bounds.items():
        if name in x:
            x[name] = x[name].clip(low, high)
    return sm.add_constant(x, has_constant="add")


def fit(frame, columns, bounds, clustered=True):
    x = design(frame, columns, bounds)
    y = frame[rm.OUTCOME].astype(float)
    if clustered:
        groups = frame["day0"].factorize()[0]
        return sm.OLS(y, x).fit(cov_type="cluster", cov_kwds={"groups": groups}), x
    return sm.OLS(y, x).fit(), x


def placebo_share(train, test, run, bounds, actual_gain, draws=PLACEBO_DRAWS, seed=rm.SEED,
                  blocks=BLOCKS, added=ADDED):
    """Share of shuffled-block draws whose dMSE is at least the actual dMSE."""
    rng = np.random.default_rng(seed)
    previous, _ = fit(train, blocks[run - 1], bounds, clustered=False)
    prev_err = test[rm.OUTCOME].to_numpy() - previous.predict(design(test, blocks[run - 1], bounds)).to_numpy()
    hits = 0
    for _ in range(draws):
        tr, te = train.copy(), test.copy()
        tr[added[run]] = tr[added[run]].to_numpy()[rng.permutation(len(tr))]
        te[added[run]] = te[added[run]].to_numpy()[rng.permutation(len(te))]
        model, _ = fit(tr, blocks[run], bounds, clustered=False)
        err = te[rm.OUTCOME].to_numpy() - model.predict(design(te, blocks[run], bounds)).to_numpy()
        hits += np.mean(prev_err ** 2) - np.mean(err ** 2) >= actual_gain
    return hits / draws


def run_sample(paths, primary_only, placebo_draws=PLACEBO_DRAWS, null_category=False,
               cutoff_filter=True, sample=None):
    sample = sample or ("primary" if primary_only else "all_events")
    frame, flow = load_sample(*paths, primary_only, null_category=null_category,
                              cutoff_filter=cutoff_filter, sample=sample)
    blocks, added = make_blocks(RUN3 + [NULL_INDICATOR] if null_category else RUN3)
    if len(frame) < rm.MIN_EVENTS:
        print(f"[{sample}] only {len(frame)} complete events: results are exploratory.")
    full_bounds = bounds_for(frame)
    train, test = rm.chronological_split(frame)
    bounds = bounds_for(train)
    actual = test[rm.OUTCOME].to_numpy(dtype=float)
    mean_err = actual - train[rm.OUTCOME].mean()

    runs, coefs, preds, errors = [], [], {}, {}
    for run in (1, 2, 3):
        full, x_full = fit(frame, blocks[run], full_bounds)
        trained, _ = fit(train, blocks[run], bounds)
        pred = trained.predict(design(test, blocks[run], bounds)).to_numpy()
        err = actual - pred
        preds[run], errors[run] = pred, err
        row = {
            "run": run, "label": LABELS[run], "sample": sample,
            "n_features": len(blocks[run]),
            "train_n": len(train), "test_n": len(test),
            "excluded_n": flow[0]["n"] - len(frame),
            "train_cutoff": train["day0"].max().date().isoformat(),
            "test_start": test["day0"].min().date().isoformat(),
            "out_of_sample_r2": 1 - np.sum(err ** 2) / np.sum(mean_err ** 2),
            "mae": np.mean(np.abs(err)), "rmse": np.sqrt(np.mean(err ** 2)),
            "in_sample_n": int(full.nobs), "in_sample_r2": full.rsquared,
            "in_sample_adj_r2": full.rsquared_adj,
            "exploratory": len(frame) < rm.MIN_EVENTS,
        }
        if run > 1:
            names = list(full.params.index)
            restriction = np.zeros((len(added[run]), len(names)))
            for i, name in enumerate(added[run]):
                restriction[i, names.index(name)] = 1
            wald = full.f_test(restriction)
            gain = errors[run - 1] ** 2 - err ** 2
            interval, n_weeks = rm.week_block_bootstrap(test, gain)
            row.update({
                "block_wald_f": float(np.squeeze(wald.fvalue)), "block_wald_p": float(wald.pvalue),
                "delta_mse_vs_previous": gain.mean(),
                "delta_mse_ci_low": interval[0], "delta_mse_ci_high": interval[1],
                "bootstrap_weeks": n_weeks,
                "placebo_share_at_least_actual": placebo_share(
                    train, test, run, bounds, gain.mean(), draws=placebo_draws,
                    blocks=blocks, added=added),
                "supported": bool(interval[0] > 0),
            })
        runs.append(row)
        sd = x_full.drop(columns="const").std(ddof=1)
        ci = full.conf_int()
        for name in blocks[run]:
            coefs.append({
                "run": run, "sample": sample, "variable": name,
                "coef": full.params[name], "std_error": full.bse[name], "p_value": full.pvalues[name],
                "coef_per_sd": full.params[name] * sd[name],
                "ci_low": ci.loc[name, 0] * sd[name], "ci_high": ci.loc[name, 1] * sd[name],
            })
    predictions = pd.DataFrame({
        "event_id": test["event_id"].to_numpy(), "ticker": test["ticker"].to_numpy(),
        "call_date": test["day0_session"].to_numpy(), "actual": actual,
        **{f"pred_run{run}": preds[run] for run in (1, 2, 3)}, "sample": sample,
    })
    return runs, coefs, predictions, flow


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cohort", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--dictionary-features", type=Path, default=DEFAULT_DICTIONARY)
    parser.add_argument("--day0-check", type=Path, default=DEFAULT_DAY0)
    parser.add_argument("--llm-scores", type=Path, required=True)
    parser.add_argument("--llm-scores-all", type=Path,
                        help="Scores for all matched calls, for the primary_all_calls row.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--data-status", default=rm.DATA_STATUS,
                        help="'cohort' for real scores; 'synthetic' for tests.")
    parser.add_argument("--placebo-draws", type=int, default=PLACEBO_DRAWS)
    parser.add_argument("--outcome-override", nargs=2, metavar=("CSV", "COLUMN"),
                        help="Replace car_0_1_pct with COLUMN from CSV (by event_id), e.g. the "
                             "Amendment 4 255-session CAR. Write to a separate --out-dir.")
    args = parser.parse_args(argv)
    cohort_path = args.cohort
    if args.outcome_override:
        source, column = args.outcome_override
        cohort = pd.read_csv(args.cohort)
        override = pd.read_csv(source)[["event_id", column]]
        cohort = cohort.drop(columns=[rm.OUTCOME]).merge(override, on="event_id", how="left",
                                                          validate="one_to_one")
        cohort = cohort.rename(columns={column: rm.OUTCOME})
        args.out_dir.mkdir(parents=True, exist_ok=True)
        cohort_path = args.out_dir / "cohort_with_outcome_override.csv"
        cohort.to_csv(cohort_path, index=False)
    paths = (cohort_path, args.dictionary_features, args.day0_check, args.llm_scores)

    runs, coefs, flows, preds = [], [], [], []
    for sample, options in VARIANTS.items():
        variant_paths = paths
        if not options.get("cutoff_filter", True):
            if args.llm_scores_all is None:
                continue
            variant_paths = paths[:3] + (args.llm_scores_all,)
        r, c, p, f = run_sample(variant_paths, options["primary_only"], args.placebo_draws,
                                null_category=options.get("null_category", False),
                                cutoff_filter=options.get("cutoff_filter", True), sample=sample)
        runs += r
        coefs += c
        flows += f
        preds.append(p)
    provenance = rm.provenance_fields(args.cohort)
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    for name, frame in (("model_runs", pd.DataFrame(runs).assign(**provenance)),
                        ("model_coefficients", pd.DataFrame(coefs)),
                        ("run_predictions", pd.concat(preds, ignore_index=True)),
                        ("nested_sample_flow", pd.DataFrame(flows))):
        frame["data_status"] = args.data_status
        frame.to_csv(out / f"{name}.csv", index=False)
    for r in runs:
        extra = ("" if r["run"] == 1 else
                 f" dMSE={r['delta_mse_vs_previous']:.3f} CI[{r['delta_mse_ci_low']:.3f},"
                 f"{r['delta_mse_ci_high']:.3f}] placebo={r['placebo_share_at_least_actual']:.3f}"
                 f" Wald p={r['block_wald_p']:.4f}")
        print(f"[{r['sample']}] Run {r['run']}: n={r['in_sample_n']} R2={r['in_sample_r2']:.4f} "
              f"OOS R2={r['out_of_sample_r2']:.4f} RMSE={r['rmse']:.3f}{extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
