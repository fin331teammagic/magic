# Specifications tried

**Purpose.** This file fixes the models, sample, split, metrics, and inference
method *before* the real holdout is evaluated, and then logs every run
(instructor audit 02, findings A2 and A3). It is append-only after the lock:
never edit or delete a dated entry; add a new one that supersedes it.

**Status:** DRAFT outline started 2026-11-17 by Michelle for Cammy to complete.
Items marked **TODO (Cammy)** need a decision. **No real holdout has been
evaluated.** The only model runs so far used synthetic data (see run log).

**Lock:** the spec is locked when every TODO in sections 1–7 is resolved and
the lock commit is recorded here. Lock commit: `TODO` · Lock date: `TODO`

---

## 1. Sample

- **Universe:** S&P 500 roster as of June 30, 2026
  (`inputs/sp500_constituents_20260630.csv`).
- **Events:** fiscal quarters ending April 1 – June 30, 2026, built by Gus
  (`docs/GUS_DATA_DICTIONARY.md`). 499 events; 4 roster stocks excluded
  (`outputs/q2_2026_exclusions.csv`).
- **Main sample:** `primary_timing_sample == True` (SEC 8-K and Yahoo agree on
  day 0): 464 events. **Robustness sample:** all 499 events.
- **Model sample:** complete cases on the outcome and every variable in the
  *largest* run, so all runs use identical events. Report the number dropped
  and why. Missing values are never filled with zero.
- **Analysis file:** `outputs/q2_2026_cohort.csv`, built by
  `code/build_cohort_dataset.py`. Record its commit hash in each run entry.

## 2. Outcomes

| Role | Column | Definition | Factor model |
|---|---|---|---|
| Checkpoint outcome (primary for CP2) | `car_0_1_pct` | AR(day 0) + AR(day 1), % | easy_es 0.1.8, Fama-French 5 (official Kenneth French daily factors), estimation 255 days, gap 50, min 100 |
| Final-study outcome | not built yet | Abnormal return summed over the 20 sessions after the reaction session, % | ETF proxies (below) |

**Provisional ETF factor proxies** (final-study outcome only; *not* Kenneth
French factors), daily total returns:

- Market excess: SPY − BIL
- Size (SMB-like): IWM − SPY
- Value (HML-like): IWD − IWF

Loadings estimated over the 252 sessions before the reaction session; the
outcome sums residuals over the forward window. SPY buy-and-hold abnormal
return is a robustness comparison.

**TODO (Cammy):** confirm which outcome the *final* prediction test uses, and
whether CAR[0,1] stays a separate reported result. The README's final design
(20-session drift) and ANALYSIS_PLAN.md's checkpoint (CAR[0,1]) differ.

## 3. Specifications (formulas)

All models: OLS with intercept. Predictors standardized using **training-set**
means and SDs only. Column names are those in `outputs/q2_2026_cohort.csv`.

**Run 1 (Yahoo Finance only)**

```
car_0_1_pct ~ eps_surprise_usd + eps_surprise_pct + log_market_cap
            + price_to_book + profit_margin_pct + debt_to_equity + beta_252d
            + return_52w_pct + ma50_ma200_gap_pct + avg_daily_volume_63d
```

Proposed removals from ANALYSIS_PLAN.md's list, with counts in the 464-event
main sample:

| Variable | Non-missing | Reason |
|---|---|---|
| `forward_pe` | 0 | Excluded by Gus: Yahoo has only a current snapshot (look-ahead) |
| `short_interest_pct_float` | 0 | Same |
| `revenue_growth_yoy_pct` | 1 | Yahoo quarterly history lacks the year-ago quarter |
| `earnings_growth_yoy_pct` | 1 | Same |

With all four kept, the complete-case sample is **0 events**; without them it
is **422**. **TODO (Cammy):** approve the removals. Also decide whether to keep
both `eps_surprise_usd` and `eps_surprise_pct`: they are highly correlated,
which inflates standard errors, but it does not break prediction.

**Run 2 (Run 1 + dictionary text):** add `transcript_sentiment`,
`management_prepared_sentiment`, `analyst_question_sentiment`,
`congratulations_mentioned`.

`sentiment_gap` (= management − analyst) is **not** entered: it is an exact
linear combination of two included columns, so OLS cannot separate the three.
Keep it for description only. **TODO (Cammy):** confirm, or drop one of the
other two and keep the gap instead.

**Run 3 (Run 2 + AI scores):** add `outlook_tone`, `guidance_specificity`.

**Final-study baseline vs. augmented (README design):**

```
baseline:  car_fwd20 ~ eps_surprise_pct + announcement_reaction
augmented: baseline + <pre-specified language scores, section 7>
```

**TODO (Cammy):** state how Runs 1–3 relate to this baseline/augmented pair
(same comparison on a different outcome, or a separate analysis).

**Robustness model (optional):** ridge regression. **TODO (Cammy):** fix the
penalty choice now (e.g. 5-fold time-ordered CV on the training set only) or
drop it. A random forest needs its hyperparameters fixed here too.

## 4. Split rule

Sort model-sample events by `day0_session` (then `event_id`). Training = the
earliest ~60%; holdout = the rest. The cut falls on a date boundary, so calls
on the same day are never split; the boundary day goes to whichever side keeps
the training share closest to 60%. The holdout is evaluated **once** per run.
No variable, filter, or model is changed after the holdout is seen; any later
change is logged as a new, exploratory specification.

## 5. Metrics

On the holdout, for each run: MAE, RMSE, and out-of-sample
R² = 1 − SSE / Σ(y − ȳ_train)². Report train n, holdout n, excluded n, the
cutoff date, and the first holdout date. **Key comparisons:** ΔRMSE and ΔR²,
Run 2 vs. Run 1 and Run 3 vs. Run 2.

## 6. Inference: is the improvement real? (audit A3)

Releases cluster between April 23 and August 19, 2026 (18 release weeks in
the main sample), so holdout errors are correlated through common market moves.
Training outcomes are realized during the holdout period. That is not
look-ahead in the predictors, but it is disclosed here.

Pre-specified procedure:

1. **Block bootstrap by release week:** resample the holdout's ISO weeks of
   `day0_session` with replacement, B = 2,000, seed = 331. Recompute ΔRMSE and
   ΔR² for each draw (models are *not* refit). Report the 2.5th–97.5th
   percentile interval.
2. **Placebo:** shuffle the added language columns across events (within the
   training and holdout sets separately), refit, and re-evaluate,
   1,000 times, seed = 331. Report the share of placebo ΔRMSE at least as
   good as the actual.

**Decision rule:** the language improvement counts as supported only if the
bootstrap interval for ΔRMSE excludes 0 **and** the placebo share is below 5%.
Otherwise report it as not distinguishable from noise. A holdout below 30
events is labelled exploratory. **TODO (Cammy):** confirm B, the seed, and the
rule.

## 7. Pre-specified language scores

| Column | Method | Version / source |
|---|---|---|
| `transcript_sentiment` | Loughran–McDonald 1993–2025 dictionary, whole call | `code/extract_transcript_features.py`; TODO (Abby) formula |
| `management_prepared_sentiment` | Same, prepared remarks only | TODO (Abby) |
| `analyst_question_sentiment` | Same, analyst questions only | TODO (Abby) |
| `congratulations_mentioned` | 1 if an analyst says "congratulat*" | TODO (Abby) |
| `outlook_tone` | LLM rubric 1–5 | TODO: model snapshot, prompt version, cutoff date |
| `guidance_specificity` | LLM rubric 1–5 | Same |

Real transcripts are **not** rights-cleared. Until they are, Runs 2–3 can
only run on synthetic text and are not evidence. **TODO (team):** the minimum
number of real scored events needed to run Runs 2–3 at all.

---

## 8. Run log

One row per run, including failed or abandoned ones. "Holdout seen" = the
real holdout metrics were computed or viewed.

| Date | Who | Spec | Data (commit) | Model n (train/holdout) | Holdout seen? | Result | Notes |
|---|---|---|---|---|---|---|---|
| 2026-11-14 | Michelle | Runs 1–3 (draft spec) | Synthetic, `code/build_synthetic_final_dataset.py` | 208 / 148 | No (synthetic only) | `outputs/synthetic_model_runs.csv` | Layout and code test; relationships planted; not evidence |
| 2026-11-17 | Michelle | File created | — | — | No | — | Outline for Cammy; no real model run |

## 9. Open decisions (summary)

1. Final-study outcome and how Runs 1–3 map to the baseline/augmented test (§2, §3).
2. Approve dropping forward P/E, short interest, and revenue/earnings growth (§3).
3. `sentiment_gap` vs. its two components (§3).
4. Ridge / random-forest robustness: fix the hyperparameters or drop it (§3).
5. Bootstrap B, seed, placebo count, and the decision rule (§6).
6. Language-score definitions and versions (Abby) and the minimum real-transcript coverage (§7).
