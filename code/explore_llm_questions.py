"""EXPLORATORY: screen the v3.0 LLM questions (and any other LLM variables).

Not pre-specified. The v3.0 questions (``docs/LLM_QUESTIONS_V3_DRAFT.md``)
were drafted after the Run 1-3 results, and Prof. Bowen is scoring them with
up to three local models. This script asks, for every model and question:

1. **Does it vary?** Value counts, nulls, modal share (``distribution.csv``).
2. **Do models agree?** Pairwise exact agreement, quadratic-weighted kappa
   and Spearman on calls both models scored (``agreement.csv``).
3. **Is it a ruler for a desk?** Spearman correlation with EPS surprise, the
   Run 2 dictionary variables and the v2.0 LLM variables, plus the
   closest other new question (``overlap.csv``). No outcome is read.
4. **Does it add anything, alone?** CAR[0,1] on Run 1 + Run 2 (the
   *baseline*, or Run 1-3 with ``--baseline run3``) plus one question.
   In-sample: coefficient, day-0-clustered p, change in R2. Holdout:
   change in MSE against the baseline refit on the same events, and the
   shuffled-score placebo share. Benjamini-Hochberg q-values within each
   model, because 20 questions x 3 models will produce "significant"
   results by chance (``one_at_a_time.csv``).
5. **Do they add anything together?** All of one model's questions as one
   block (``block.csv``). Nulls in the block are coded 0 with a
   "not discussed" indicator, so the sample does not collapse.

A ``consensus`` pseudo-model (the mean of the models' scores for each call)
is added when two or more models are given.

Input: score CSVs in the layout ``code/score_transcripts_edsl.py`` writes
(``id``, one column per variable, ``status``, ``parse_status``). One model
may come in several files, one per prompt group; they are joined on ``id``.
A row counts only if it parsed and has ``status == "scored"``; failed rows
and nulls stay missing and are never turned into zero (except as described
for the block). Every value is checked against the rubric below, so a file
scored with a different prompt fails loudly instead of being analysed.

Sample: as Runs 12-19 (primary timing sample, call after the 2026-06-30
cutoff, day 0 consistent with the call, Run 1-2 complete). The holdout
split date is fixed once on that base sample, so every question uses the
same training/holdout dates. The holdout has already been looked at
(runs 12-19), so holdout numbers here are exploratory too.

    python code/explore_llm_questions.py \\
        --scores gemma4=outputs/llm_scores_real/q2_2026_llm_scores_v2.0_gemma4_after_cutoff395.csv \\
        --out-dir outputs/exploratory_llm_questions

    # v3.0, one model per --scores, each model's prompt groups comma-separated:
    python code/explore_llm_questions.py \\
        --scores modelA=a_grpA.csv,a_grpB.csv,a_grpC.csv,a_grpD.csv \\
        --scores modelB=b_all20.csv \\
        --reference-llm outputs/llm_scores_real/q2_2026_llm_scores_v2.0_gemma4_after_cutoff395.csv
"""

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compare_llm_runs as cl  # noqa: E402
import run_models as rm  # noqa: E402
import run_nested_models as nm  # noqa: E402

DEFAULT_OUT = Path("outputs/exploratory_llm_questions")
PLACEBO_DRAWS = 500
LOW_VARIATION_SHARE = 0.90
CONSENSUS = "consensus"

# Rubric: variable -> (prompt group, allowed non-null values, null allowed).
# v2.0 from prompts/transcript_llm_scores_v2.0.txt; v3.0 from
# docs/LLM_QUESTIONS_V3_DRAFT.md. Update here if the v3.0 rubric changes.
QUESTIONS = {
    "guidance_specificity": ("v2.0", {0, 1, 2}, True),
    "guidance_revision": ("v2.0", {-1, 0, 1}, True),
    "qa_evasiveness": ("v2.0", {0, 1, 2}, True),
    "one_off_attribution": ("v2.0", {-1, 0, 1}, True),
    "analyst_concern_focus": ("v2.0", {0, 1, 2}, True),
    # Group A: outlook
    "outlook_vs_quarter": ("v3.0-A", {-1, 0, 1}, False),
    "margin_outlook": ("v3.0-A", {-1, 0, 1}, True),
    "demand_trend": ("v3.0-A", {-1, 0, 1}, True),
    "back_half_dependence": ("v3.0-A", {0, 1}, False),
    "guidance_framing": ("v3.0-A", {-1, 0, 1}, False),
    # Group B: business and capital decisions
    "pricing_power": ("v3.0-B", {-1, 0, 1}, True),
    "competitive_pressure": ("v3.0-B", {0, 1, 2}, False),
    "capex_change": ("v3.0-B", {-1, 0, 1}, False),
    "capital_return_change": ("v3.0-B", {-1, 0, 1}, False),
    "cost_program": ("v3.0-B", {0, 1, 2}, False),
    # Group C: Q&A and disclosure
    "qa_vs_prepared": ("v3.0-C", {-1, 0, 1}, True),
    "analyst_pushback": ("v3.0-C", {0, 1, 2}, True),
    "new_adverse_disclosure": ("v3.0-C", {0, 1}, False),
    "missed_own_target": ("v3.0-C", {0, 1}, False),
    "external_attribution": ("v3.0-C", {0, 1, 2}, False),
    # Group D: context
    "balance_sheet_concern": ("v3.0-D", {0, 1}, False),
    "leadership_change": ("v3.0-D", {0, 1}, False),
    "corporate_action": ("v3.0-D", {0, 1}, False),
    "ai_emphasis": ("v3.0-D", {0, 1, 2}, False),
    "expected_investor_reaction": ("v3.0-D", {-1, 0, 1}, False),
}
REFERENCE = ["eps_surprise_pct", *nm.RUN2]


# ---------------------------------------------------------------- loading

def read_score_file(path):
    """Valid scored rows of one file: ``event_id`` plus the rubric variables it has."""
    raw = pd.read_csv(path, na_values=["null"], keep_default_na=True)
    if "id" not in raw:
        raise ValueError(f"{path}: no 'id' column.")
    if raw["id"].duplicated().any():
        raise ValueError(f"{path}: duplicate ids, e.g. {raw.loc[raw['id'].duplicated(), 'id'].iloc[0]}")
    variables = [name for name in QUESTIONS if name in raw.columns]
    if not variables:
        raise ValueError(f"{path}: none of the known question columns are present.")
    keep = pd.Series(True, index=raw.index)
    if "parse_status" in raw:
        keep &= raw["parse_status"] == "ok"
    if "status" in raw:
        keep &= raw["status"] == "scored"
    frame = raw.loc[keep, ["id", *variables]].rename(columns={"id": "event_id"})
    for name in variables:
        _, allowed, nullable = QUESTIONS[name]
        values = frame[name]
        bad = values.dropna()[~values.dropna().isin(allowed)]
        if len(bad):
            raise ValueError(f"{path}: {name} has values outside {sorted(allowed)}: {sorted(bad.unique())[:5]}")
        if not nullable and values.isna().any():
            raise ValueError(f"{path}: {name} is null for {int(values.isna().sum())} scored rows, "
                             "but the rubric has no null option.")
        frame[name] = values.astype(float)
    return frame, len(raw)


def load_model(paths):
    """Join one model's prompt-group files on ``event_id``.

    Returns (frame, valid, file report). ``valid[variable]`` is the set of
    calls whose row for that variable's file parsed and was scored, so a
    null answer can be told apart from a failed prompt group after the join.
    """
    merged, report, seen, valid = None, [], {}, {}
    for path in paths:
        frame, n_rows = read_score_file(path)
        for name in frame.columns.drop("event_id"):
            if name in seen:
                raise ValueError(f"{name} appears in both {seen[name]} and {path}.")
            seen[name] = path
            valid[name] = set(frame["event_id"])
        report.append({"file": str(path), "rows": n_rows, "valid_rows": len(frame),
                       "variables": " ".join(frame.columns.drop("event_id"))})
        merged = frame if merged is None else merged.merge(frame, on="event_id", how="outer",
                                                           validate="one_to_one")
    return merged, valid, report


def parse_scores_arg(values):
    """``label=path[,path...]`` -> {label: [Path, ...]} in the order given."""
    models = {}
    for value in values:
        label, sep, paths = value.partition("=")
        if not sep or not label or not paths:
            raise ValueError(f"--scores must look like label=path[,path]: {value!r}")
        if label in models or label == CONSENSUS:
            raise ValueError(f"Model label {label!r} is repeated or reserved.")
        models[label] = [Path(p) for p in paths.split(",") if p]
    return models


def add_consensus(models, valid):
    """Per call and question, the mean of the models that scored it (non-null).

    Returns (frame, valid) or (None, None). Only questions every model has
    are included. A call is valid for the consensus if any model's row was.
    """
    if len(models) < 2:
        return None, None
    shared = sorted(set.intersection(*(set(f.columns.drop("event_id")) for f in models.values())),
                    key=list(QUESTIONS).index)
    if not shared:
        return None, None
    stacked = pd.concat([f[["event_id", *shared]] for f in models.values()])
    frame = stacked.groupby("event_id", as_index=False)[shared].mean()
    return frame, {name: set.union(*(v[name] for v in valid.values())) for name in shared}


def base_sample(cohort_path, dictionary_path, day0_path, primary_only=True, baseline_llm=None):
    """Run 1-2 (or 1-3) complete-case sample, as runs 12-19, before any new question."""
    cohort = pd.read_csv(cohort_path)
    for name, column in rm.RUN1.items():
        cohort[name] = cohort[column]
    text = pd.read_csv(dictionary_path)[["event_id", "after_training_cutoff", *nm.RUN2]]
    day0 = pd.read_csv(day0_path)[["event_id", "day0_check"]]
    frame = (cohort.merge(text, on="event_id", how="left", validate="one_to_one")
             .merge(day0, on="event_id", how="left", validate="one_to_one"))
    base_columns = list(rm.RUN1) + nm.RUN2
    if baseline_llm is not None:
        llm, _ = read_score_file(baseline_llm)
        frame = frame.merge(llm[["event_id", *nm.RUN3]], on="event_id", how="left",
                            validate="one_to_one")
        base_columns += nm.RUN3
    flow = [("cohort events", len(frame))]
    masks = []
    if primary_only:
        masks.append(("primary_timing_sample == True", frame["primary_timing_sample"] == True))  # noqa: E712
    masks += [("call after 2026-06-30 cutoff", frame["after_training_cutoff"] == True),  # noqa: E712
              ("day 0 consistent with call", frame["day0_check"] == "consistent_with_call")]
    for step, mask in masks:
        frame = frame[mask.loc[frame.index]]
        flow.append((step, len(frame)))
    for column in [rm.OUTCOME, *base_columns]:
        frame = frame[frame[column].notna()]
        flow.append((f"{column} present", len(frame)))
    frame = frame.copy()
    frame["timestamp_utc"] = pd.to_datetime(frame["earnings_timestamp"], utc=True)
    frame["day0"] = pd.to_datetime(frame["day0_session"])
    frame = frame.sort_values(["timestamp_utc", "event_id"]).reset_index(drop=True)
    return frame, base_columns, pd.DataFrame(flow, columns=["step", "n"])


# ---------------------------------------------------------------- descriptives

def distribution(model, frame, valid, sample_ids):
    rows = []
    frame = frame[frame["event_id"].isin(sample_ids)]
    for name in frame.columns.drop("event_id"):
        ok = valid[name] & sample_ids
        values = frame.loc[frame["event_id"].isin(ok), name]
        counts = values.value_counts()
        rows.append({
            "model": model, "variable": name, "group": QUESTIONS[name][0],
            "n_sample": len(sample_ids), "n_valid_row": len(ok),
            "n_scored": int(values.notna().sum()), "n_null": int(values.isna().sum()),
            "n_no_valid_row": len(sample_ids) - len(ok),
            "mean": values.mean(), "sd": values.std(),
            **{f"count_{k}": int((values == k).sum()) for k in (-1, 0, 1, 2)},
            "modal_share": counts.max() / counts.sum() if counts.sum() else np.nan,
            "low_variation": bool(counts.sum() and counts.max() / counts.sum() > LOW_VARIATION_SHARE),
        })
    return rows


def agreement(models, sample_ids):
    rows = []
    for (a, fa), (b, fb) in itertools.combinations(models.items(), 2):
        joined = (fa[fa["event_id"].isin(sample_ids)]
                  .merge(fb, on="event_id", suffixes=("_a", "_b")))
        shared = [n for n in QUESTIONS if f"{n}_a" in joined and f"{n}_b" in joined]
        for name in shared:
            x, y = joined[f"{name}_a"], joined[f"{name}_b"]
            both = x.notna() & y.notna()
            rows.append({
                "variable": name, "model_a": a, "model_b": b, "n_calls": len(joined),
                "n_both_scored": int(both.sum()),
                "exact_agreement": float(((x == y) | (x.isna() & y.isna())).mean()),
                "weighted_kappa": cl.weighted_kappa(x[both], y[both]) if both.sum() else np.nan,
                "spearman": x[both].corr(y[both], method="spearman") if both.sum() > 2 else np.nan,
                "null_in_one_only": int((x.isna() ^ y.isna()).sum()),
            })
    return rows


def overlap(model, frame, base, reference_llm=None):
    """Spearman of each new question with Run 1-2 references and the other new questions."""
    joined = base[["event_id", *REFERENCE]].merge(frame, on="event_id", how="left")
    references = list(REFERENCE)
    if reference_llm is not None:
        ref, _ = read_score_file(reference_llm)
        ref = ref[["event_id", *[c for c in nm.RUN3 if c in ref]]]
        ref = ref.rename(columns={c: f"v2_{c}" for c in nm.RUN3})
        joined = joined.merge(ref, on="event_id", how="left")
        references += [f"v2_{c}" for c in nm.RUN3 if f"v2_{c}" in joined]
    new = [c for c in frame.columns.drop("event_id") if f"v2_{c}" not in references]
    corr = joined[references + new].corr(method="spearman", min_periods=20)
    rows = []
    for name in new:
        ref_corr = corr.loc[name, references].drop(f"v2_{name}", errors="ignore")
        other = corr.loc[name, new].drop(name)
        row = {"model": model, "variable": name, **{f"rho_{r}": ref_corr.get(r) for r in references}}
        row["max_abs_rho_reference"] = ref_corr.abs().max()
        row["closest_reference"] = ref_corr.abs().idxmax() if ref_corr.notna().any() else ""
        row["max_abs_rho_other_new"] = other.abs().max() if len(other) else np.nan
        row["closest_other_new"] = other.abs().idxmax() if other.notna().any() else ""
        rows.append(row)
    return rows


# ---------------------------------------------------------------- models

def _matrix(frame, columns, bounds):
    return nm.design(frame, columns, bounds).to_numpy(dtype=float)


def _predict(x_train, y_train, x_test):
    beta, *_ = np.linalg.lstsq(x_train, y_train, rcond=None)
    return x_test @ beta


def incremental(frame, base_columns, added, train_mask, placebo_draws, seed=rm.SEED):
    """In-sample and holdout gain of ``added`` columns over ``base_columns`` on ``frame``."""
    columns = base_columns + added
    full_bounds = nm.bounds_for(frame)
    base_fit, _ = nm.fit(frame, base_columns, full_bounds)
    full_fit, x_full = nm.fit(frame, columns, full_bounds)
    names = list(full_fit.params.index)
    restriction = np.zeros((len(added), len(names)))
    for i, name in enumerate(added):
        restriction[i, names.index(name)] = 1
    wald = full_fit.f_test(restriction)
    out = {
        "n": int(full_fit.nobs), "n_clusters": int(frame["day0"].nunique()),
        "coef": full_fit.params[added[0]], "std_error": full_fit.bse[added[0]],
        "p_value": full_fit.pvalues[added[0]],
        "coef_per_sd": full_fit.params[added[0]] * x_full[added[0]].std(ddof=1),
        "block_wald_p": float(wald.pvalue),
        "in_sample_r2_base": base_fit.rsquared, "in_sample_r2": full_fit.rsquared,
        "delta_r2": full_fit.rsquared - base_fit.rsquared,
        "delta_adj_r2": full_fit.rsquared_adj - base_fit.rsquared_adj,
    }
    train, test = frame[train_mask], frame[~train_mask]
    out.update({"train_n": len(train), "test_n": len(test)})
    if len(test) < 10 or len(train) < len(columns) + 10:
        return out | {"delta_mse": np.nan, "placebo_share": np.nan, "oos_r2": np.nan}
    bounds = nm.bounds_for(train)
    y_tr = train[rm.OUTCOME].to_numpy(float)
    y_te = test[rm.OUTCOME].to_numpy(float)
    base_err = y_te - _predict(_matrix(train, base_columns, bounds), y_tr,
                               _matrix(test, base_columns, bounds))
    x_tr, x_te = _matrix(train, columns, bounds), _matrix(test, columns, bounds)
    err = y_te - _predict(x_tr, y_tr, x_te)
    gain = np.mean(base_err ** 2) - np.mean(err ** 2)
    cols = [columns.index(a) + 1 for a in added]  # +1 for the constant
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(placebo_draws):
        p_tr, p_te = x_tr.copy(), x_te.copy()
        p_tr[:, cols] = p_tr[rng.permutation(len(p_tr))][:, cols]
        p_te[:, cols] = p_te[rng.permutation(len(p_te))][:, cols]
        p_err = y_te - _predict(p_tr, y_tr, p_te)
        hits += np.mean(base_err ** 2) - np.mean(p_err ** 2) >= gain
    mean_err = y_te - y_tr.mean()
    return out | {
        "delta_mse": gain,
        "placebo_share": hits / placebo_draws if placebo_draws else np.nan,
        "oos_r2": 1 - np.sum(err ** 2) / np.sum(mean_err ** 2),
        "oos_r2_base": 1 - np.sum(base_err ** 2) / np.sum(mean_err ** 2),
    }


def null_coded(frame, name):
    """Copy with ``name`` null -> 0 and a ``name__not_discussed`` indicator."""
    frame = frame.copy()
    indicator = f"{name}__not_discussed"
    frame[indicator] = frame[name].isna().astype(float)
    frame[name] = frame[name].fillna(0)
    return frame, indicator


def benjamini_hochberg(p):
    p = np.asarray(p, dtype=float)
    q = np.full(len(p), np.nan)
    ok = ~np.isnan(p)
    if not ok.any():
        return q
    order = np.argsort(p[ok])
    ranked = p[ok][order] * ok.sum() / np.arange(1, ok.sum() + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1].clip(max=1)
    q_ok = np.empty(ok.sum())
    q_ok[order] = ranked
    q[ok] = q_ok
    return q


def one_at_a_time(model, frame, valid, base, base_columns, cutoff, placebo_draws):
    rows = []
    joined = base.merge(frame, on="event_id", how="left")
    for name in frame.columns.drop("event_id"):
        variants = [("dropped", joined[joined[name].notna()], [name])]
        if QUESTIONS[name][2] and joined[name].isna().any():
            coded, indicator = null_coded(joined[joined["event_id"].isin(valid[name])], name)
            if coded[indicator].sum() >= 5:
                variants.append(("coded_0_plus_indicator", coded, [name, indicator]))
        for handling, sample, added in variants:
            sample = sample.reset_index(drop=True)
            row = {"model": model, "variable": name, "group": QUESTIONS[name][0],
                   "null_handling": handling}
            if sample[name].nunique() < 2:
                rows.append(row | {"n": len(sample), "note": "no variation in sample"})
                continue
            row.update(incremental(sample, base_columns, added, sample["day0"] <= cutoff, placebo_draws))
            rows.append(row)
    result = pd.DataFrame(rows)
    if result.empty:
        return []
    result["bh_q_within_model"] = np.nan
    primary = result["null_handling"] == "dropped"
    result.loc[primary, "bh_q_within_model"] = benjamini_hochberg(result.loc[primary, "p_value"])
    return result.to_dict("records")


def block(model, frame, valid, base, base_columns, cutoff, placebo_draws):
    """All questions together; calls must have a valid row in every prompt group."""
    every = set.intersection(*valid.values())
    joined = base.merge(frame[frame["event_id"].isin(every)], on="event_id", how="inner")
    added = []
    for name in frame.columns.drop("event_id"):
        if joined[name].nunique() < 2:
            continue
        if joined[name].isna().any():
            joined, indicator = null_coded(joined, name)
            if joined[indicator].nunique() > 1:
                added.append(indicator)
        added.append(name)
    joined = joined.reset_index(drop=True)
    stats = incremental(joined, base_columns, added, joined["day0"] <= cutoff, placebo_draws)
    for key in ("coef", "std_error", "p_value", "coef_per_sd"):
        stats.pop(key)
    return {"model": model, "n_questions": sum(not a.endswith("__not_discussed") for a in added),
            "n_added_columns": len(added), "added": " ".join(added), **stats}


# ---------------------------------------------------------------- main

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--scores", action="append", required=True,
                        help="label=path[,path...]; repeat once per model.")
    parser.add_argument("--reference-llm", type=Path,
                        help="v2.0 scores, for overlap correlations (e.g. the Gemma after-cutoff file).")
    parser.add_argument("--baseline", choices=["run2", "run3"], default="run2",
                        help="run3 adds the v2.0 variables from --reference-llm to the baseline.")
    parser.add_argument("--all-events", action="store_true", help="Drop the primary-timing filter.")
    parser.add_argument("--cohort", type=Path, default=nm.DEFAULT_COHORT)
    parser.add_argument("--dictionary-features", type=Path, default=nm.DEFAULT_DICTIONARY)
    parser.add_argument("--day0-check", type=Path, default=nm.DEFAULT_DAY0)
    parser.add_argument("--placebo-draws", type=int, default=PLACEBO_DRAWS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    if args.baseline == "run3" and args.reference_llm is None:
        parser.error("--baseline run3 needs --reference-llm.")

    specs = parse_scores_arg(args.scores)
    models, valid, files = {}, {}, []
    for label, paths in specs.items():
        models[label], valid[label], report = load_model(paths)
        files += [{"model": label, **r} for r in report]
    consensus, consensus_valid = add_consensus(models, valid)
    analysed = dict(models)
    if consensus is not None:
        analysed[CONSENSUS], valid[CONSENSUS] = consensus, consensus_valid

    base, base_columns, flow = base_sample(
        args.cohort, args.dictionary_features, args.day0_check, primary_only=not args.all_events,
        baseline_llm=args.reference_llm if args.baseline == "run3" else None)
    train, _ = rm.chronological_split(base)
    cutoff = train["day0"].max()
    ids = set(base["event_id"])
    print(f"Base sample: {len(base)} events; training day 0 through {cutoff.date()}, "
          f"holdout {len(base) - len(train)} events. Baseline: {args.baseline} "
          f"({len(base_columns)} variables).")

    dist, agree, over, single, blocks = [], agreement(models, ids), [], [], []
    for label, frame in analysed.items():
        dist += distribution(label, frame, valid[label], ids)
        over += overlap(label, frame, base, args.reference_llm)
        single += one_at_a_time(label, frame, valid[label], base, base_columns, cutoff,
                                args.placebo_draws)
        blocks.append(block(label, frame, valid[label], base, base_columns, cutoff,
                            args.placebo_draws))

    provenance = rm.provenance_fields(args.cohort) | {
        "outcome": rm.OUTCOME, "sample": "all_events" if args.all_events else "primary",
        "baseline": args.baseline, "holdout_train_through": cutoff.date().isoformat(),
        "status": "EXPLORATORY (not pre-specified)",
    }
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("score_files", files), ("distribution", dist), ("agreement", agree),
                       ("overlap", over), ("one_at_a_time", single), ("block", blocks)):
        pd.DataFrame(rows).assign(**provenance).to_csv(out / f"{name}.csv", index=False)
    flow.assign(**provenance).to_csv(out / "sample_flow.csv", index=False)

    table = pd.DataFrame(single)
    if not table.empty:
        view = table[table["null_handling"] == "dropped"].sort_values("p_value")
        columns = ["model", "variable", "n", "coef", "p_value", "bh_q_within_model",
                   "delta_r2", "delta_mse", "placebo_share"]
        with pd.option_context("display.width", 200, "display.max_rows", 200):
            print(view[[c for c in columns if c in view]].round(4).to_string(index=False))
    for row in blocks:
        print(f"[{row['model']}] all {row['n_questions']} questions as one block: n={row['n']} "
              f"dR2={row['delta_r2']:.3f} Wald p={row['block_wald_p']:.4f} "
              f"dMSE={row['delta_mse']:.3f} placebo={row['placebo_share']:.3f}")
    print(f"Wrote {out}/ (EXPLORATORY).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
