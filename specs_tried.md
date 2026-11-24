# Specifications tried

Team Magic · responds to instructor audit findings A2 and A3
(`audits/02_instructor_audit.md`).

This file fixes the analysis **before any model is fit on real data or the
holdout is evaluated**, then logs every model run in order. Sections 1–7 are
the pre-specification. Once the first real-data run is logged, they are not
edited. Any later change is added as a dated amendment in Section 8, and
results produced after a change are labeled as not pre-specified.

> **Status:** FROZEN 2026-11-22 (Amendment 1). Drafted 2026-11-19. No model
> had been fit on real data when it was frozen. When it was frozen, the only
> runs in `outputs/` used the synthetic 500-call fixture. The **[TEAM]** items
> below were settled in Amendments 1 and 5. Real-data runs are logged in §8
> (runs 4–5 and 12–19).

## 1. Question and design

Do variables measured by an LLM from the earnings call add explanatory and
predictive power for the abnormal return around the call, beyond:

- standard fundamental predictors (Run 1), and
- standard, non-AI text-analysis measures (Run 2)?

Following the course lead's guidance (in class, November 2026), the design is
**three nested OLS regressions on the same events**, each adding one block of
about five variables:

| Run | Adds | Answers |
|---|---|---|
| 1 | Fundamental variables | Baseline |
| 2 | + classic text-analysis variables | What standard text tools add beyond fundamentals |
| 3 | + LLM-measured variables | What the LLM adds beyond both |

**Rule for LLM variables:** each one must measure something the Run 1 and
Run 2 variables don't already measure, for example because it depends on
context, nuance or interpretation. We don't use the LLM to re-measure
earnings surprise or overall sentiment, which we already measure
directly.

The 20-session post-announcement drift question in `README.md` becomes a
secondary analysis (Section 6).

## 2. Sample

- **Universe:** the 503-stock S&P 500 roster dated 2026-06-30
  (`inputs/sp500_constituents_20260630.csv`, Wikipedia revision
  `1361794875`). Firms that later leave the index stay in.
- **Events:** company-quarter calls for fiscal quarters ending 2026-04-01
  through 2026-06-30. The current cohort file is `outputs/q2_2026_cohort.csv`,
  with 499 events, 492 of which have CAR[0,1].
- **Primary sample:** events with `primary_timing_sample == True`.
  Robustness: all events.
- **Same sample in every run:** all three runs use only events with every
  Run 1–3 variable present (complete case). We report how many events each
  variable removes. A missing value stays missing and is never set to zero.
  An event with no transcript drops out of all three runs, so the comparison
  stays like-for-like.
- **Minimum size [TEAM]:** proposed rule: if the complete-case sample has
  fewer than 50 events, all results are reported as exploratory.

## 3. Outcome

- **Primary outcome:** `car_0_1_pct`, the cumulative abnormal return over the
  call's day 0 and day 1, from easy_es 0.1.8 with the official Fama–French
  five daily factors (CRSP 202609 vintage). Definitions and estimation window
  are in `docs/GUS_DATA_DICTIONARY.md`.
- **Day 0:** the first session on which the release could be traded. A
  release after the close maps to the next session.
- No predictor may use prices or volumes from day 0 or day 1.

## 4. Variables

All predictors are measured with information available before the call
(Run 1) or from the call transcript itself (Runs 2–3).

### Run 1: fundamentals (5)

| Variable | Definition |
|---|---|
| `eps_surprise_pct` | (actual − consensus) / \|consensus\| × 100 |
| `log_market_cap` | log of market cap on the last session before the call |
| `price_to_book` | price-to-book on the last session before the call |
| `price_change_52w_pct` | 52-week price change to the last session before the call (momentum) |
| `beta` | market beta from Yahoo |

- Consensus EPS is Yahoo's figure and is **not** verified as point-in-time
  (`observed_consensus_not_pit`). This is a disclosed limitation.
- Left out of the primary specification: `forward_pe` and `short_pct_float`
  (Yahoo only gives current snapshots, a look-ahead risk), and the other
  Yahoo fields in `outputs/final_dataset_variables.csv`. They can be added
  in a robustness run labeled as such.
- **[TEAM]** Winsorizing: proposed rule is to winsorize `eps_surprise_pct`
  and `price_to_book` at the 1st and 99th percentiles of the training set.

### Run 2: classic text analysis (5)

Loughran–McDonald 1993–2025 Master Dictionary, computed locally by
`code/extract_transcript_features.py` (definitions in
`docs/transcript_features/data_dictionary.md`):

| Variable | Definition |
|---|---|
| `transcript_sentiment` | (positive − negative) / words, whole call |
| `management_prepared_sentiment` | the same, management prepared remarks |
| `analyst_question_sentiment` | the same, analyst turns |
| `uncertainty_word_proportion` | uncertainty words / words, whole call |
| `congratulations_mentioned` | 1 if an analyst says "congratulations" or "congrats" |

`sentiment_gap` is excluded because it is an exact linear combination of two
of these (collinear).

### Run 3: LLM-measured (5) [TEAM]

Proposed variables, scored from the transcript only:

| Variable | Scale | What it captures | Why a dictionary can't |
|---|---|---|---|
| `guidance_specificity` | 0–2 | Whether forward guidance is absent, qualitative or numeric (existing rubric, prompt v1.2) | Needs to tell "we expect growth" apart from "revenue of $4–4.2B in Q3" |
| `guidance_revision` | −1, 0, +1, null | Whether management raised, kept or cut its prior guidance, as stated on the call | Needs to understand what is being compared with what |
| `qa_evasiveness` | 0–2 | How often management fails to directly answer analysts' questions | Needs to match each answer to its question |
| `one_off_attribution` | −1, 0, +1 | Whether management credits or blames the quarter's results on temporary, one-time factors | Needs to understand causal explanations |
| `analyst_concern_focus` | 0–2 | Whether analysts' questions focus on a single problem the company has | Needs the topics of the questions, not just their tone |

- `outlook_tone` (prompt v1.2) is **dropped** from the primary run under the
  rule in Section 1, because it largely re-measures sentiment. It may appear
  in a robustness run.
- **Rubric:** the exact definitions and thresholds are in the frozen prompt
  `prompts/transcript_llm_scores_v2.0.txt` (branch `abby/llm-rubric-v2`),
  scored by `code/score_transcripts_edsl.py`. If the table above and the
  prompt differ, the prompt governs. The prompt is checked on the 12-call
  synthetic development set and then, unchanged, on the 8-call validation set
  before any real transcript is scored. Both runs are recorded in Section 8.
- **Input:** only the transcript text for that call. No returns, prices,
  news or dates after the call. The prompt tells the model to treat the
  transcript as data and to ignore any instructions inside it.
- **Model [TEAM]:** proposed Claude Sonnet 5.5 (`claude-sonnet-5-5`), because
  the new variables need more judgment than v1.2. Effort is set by a
  synthetic-only comparison before freezing. Record the model ID, effort,
  prompt version and run date with every score.
- **Knowledge cutoff [TO VERIFY]:** record the cutoff Anthropic publishes for
  the chosen model, with the link and the date checked. The cohort's calls
  were in July–August 2026. A cutoff before the calls lowers the leakage risk
  but does not prove the events are absent from training.
- **Execution:** each call is scored once with the frozen prompt. Calls that
  fail or don't parse are retried at most twice, then recorded as missing.
  Transcript text and raw model outputs are not committed.
- **Transcript coverage [TEAM]:** the course's licensed transcript dataset
  (S&P Capital IQ via WRDS, kept locally in git-ignored `restricted_data/`)
  covers calls from 2024-01-05 to 2025-12-19. It does **not** include the
  July–August 2026 calls in the Q2 2026 cohort. Either find a permitted
  source for the 2026 calls or change the cohort to a quarter the dataset
  covers. Changing the cohort would also change the LLM leakage question,
  because 2024–2025 calls fall before every current Claude model's cutoff.
- **Rights:** scoring real transcripts requires a cleared source and written
  approval from the course lead to send transcript text to the model
  provider (`STATUS.md` still records a prohibition).

## 5. Estimation and evaluation

### In-sample (primary)

- OLS with an intercept, for Runs 1, 2 and 3 on the full complete-case
  sample.
- **Standard errors:** clustered by day-0 trading date, because events that
  report on the same day share market moves.
- **Incremental value of each block:**
  - the change in R² and adjusted R² from Run 1 to 2 and from Run 2 to 3;
  - a clustered Wald test that the added block's coefficients are jointly
    zero.
- Report every coefficient with its clustered standard error.

### Chronological holdout (prediction check)

- Sort by `earnings_timestamp` (UTC). The first 60% of events are the
  training set and the last 40% the holdout. The boundary moves forward to
  the end of a trading date, so no day-0 date appears in both sets.
- Fit each run on the training set only, then evaluate the holdout **once**.
- **Metrics:**
  - out-of-sample R², against the training-set mean;
  - MAE and RMSE;
  - the improvement, ΔMSE = MSE(previous run) − MSE(this run), for Run 2 vs 1
    and Run 3 vs 2.

### Inference for correlated holdout errors (A3)

Holdout events reporting in the same weeks share market conditions, so their
errors are correlated. We judge each ΔMSE in two pre-specified ways:

1. **Week-block bootstrap (primary).** Resample calendar weeks of day 0
   (Monday–Sunday) with replacement, 2,000 times, seed 331. Recompute ΔMSE
   from the fixed holdout predictions in each draw and report the 95%
   percentile interval. The improvement counts as **supported** only if the
   interval lies entirely above zero.
2. **Shuffled-score placebo.** Permute the added block's columns jointly
   across events, separately within the training set and within the holdout,
   then refit and recompute ΔMSE, 1,000 times, seed 331. Report the share of
   placebo draws at or above the actual ΔMSE.

**Disclosed overlap:** CAR[0,1] windows are two sessions long, so a training
outcome and a holdout outcome barely overlap in time. The 20-session
secondary outcome overlaps heavily. Training returns are realized during
holdout events' windows, so that analysis is not a clean out-of-period test,
and we say so next to its table.

## 6. Secondary and robustness analyses

These are labeled secondary and don't change the primary conclusion:

- The same three runs with the 20-session post-announcement factor-proxy
  outcome `factor_proxy_abnormal_20d_return_pct`. The day-0/1 reaction is
  added as a Run 1 control. The ETF proxies, *not* French factors, are SPY −
  BIL, IWM − SPY and IWD − IWF, with loadings estimated over 252 sessions
  before the reaction session and windows sliced by date (A5).
- All events, ignoring `primary_timing_sample`.
- `outlook_tone` added to Run 3.
- The fuller Yahoo variable set in Run 1.
- **[TEAM]** Ridge regression as a prediction robustness check, with the
  penalty chosen by time-ordered cross-validation inside the training set
  only.

## 7. Reporting rules

- Report the result of each step whether it is positive, null or negative.
- Every number in the write-up traces to a file in `outputs/` and a dated run
  in Section 8.
- Report sample counts at each filter step.

## 8. Run log

One entry per model fit, scoring run or evaluation, in order, including
failed and discarded runs.

| # | Date | Who | Data | Outcome | Specification | n | Holdout evaluated? | Output |
|---|---|---|---|---|---|---|---|---|
| 0 | 2026-11-14 | Michelle | synthetic 500-call fixture | CAR[0,1] | `ANALYSIS_PLAN.md` Runs 1–3 (earlier variable list) | 208 / 148 | synthetic only, not study data | `outputs/synthetic_model_runs.csv` |
| 1 | 2026-11-19 | Abby | — | — | Pre-specification drafted (this file) | — | No | — |
| 2 | 2026-11-22 | Abby | — | — | Merged `abby/specs-tried` and `michelle-pins-and-specs`. This file supersedes Michelle's Nov 17 draft (`468ec02`). Amendments 1–2 below written; §1–7 frozen | — | No | — |
| 3 | 2026-11-22 | Abby | synthetic v2.0 development set (12 invented calls) | rubric agreement | `claude-haiku-5-5`, effort low, prompt v2.0, `code/score_transcripts_edsl.py` | 12 | n/a (synthetic) | `outputs/synthetic_v2_development_haiku_scores.csv` |
| 4 | 2026-11-22 | Abby | real cohort, `outputs/q2_2026_cohort.csv` @ `a6ef269`, primary sample | CAR[0,1] | Run 1 (Amendment 1), `code/run_models.py` @ `971e1a3` | 426 in-sample; 292 / 134 | **Yes, once** | `outputs/model_comparison_metrics.csv` (`baseline`), `holdout_predictions.csv`, `run1_coefficients.csv`, `run1_sample_flow.csv` |
| 5 | 2026-11-22 | Abby | same, all events (robustness) | CAR[0,1] | same | 433 in-sample; 294 / 139 | **Yes, once** | `model_comparison_metrics.csv` (`baseline_all_events`), `run1_coefficients.csv` |
| 6 | 2026-11-22 | Abby | synthetic v2.0 development set | rubric agreement | `claude-sonnet-5-5`, effort low, prompt v2.0 | 12 | n/a (synthetic) | `outputs/synthetic_v2_development_sonnet_scores.csv` |
| 7 | 2026-11-22 | Abby | synthetic v2.0 validation set (8 invented calls), prompt unchanged | rubric agreement | `claude-haiku-5-5`, effort low, prompt v2.0 | 8 | n/a (synthetic) | `outputs/synthetic_v2_validation_haiku_scores.csv` |
| 8 | 2026-11-22 | Abby | same | rubric agreement | `claude-sonnet-5-5`, effort low, prompt v2.0 | 8 | n/a (synthetic) | `outputs/synthetic_v2_validation_sonnet_scores.csv` |
| 9 | 2026-11-22 | Abby | 474 matched real calls (local only; nothing sent) | — | Run 2 dictionary features, `code/build_dictionary_features.py` (Amendment 3). Feature build only, no model fit | 474 | No | `outputs/q2_2026_dictionary_features.csv` |
| 10 | 2026-11-23 | Prof. Bowen | 474 matched real calls, on his own computer (nothing sent off it) | — | Run 3 LLM scoring: prompt v2.0 (SHA-256 `9a9bc0cb…`), Gemma 4 26B-A4B-it (Q6_K_XL GGUF), llama.cpp, EDSL 1.0.9 with remote features off, temperature 0. Scoring only, no model fit. Synthetic validation 8/8 calls agree on every field; development 12/12 parsed, 1 disagreement | 474 (472 parsed); 395 after the cutoff (394 parsed) | No | `outputs/llm_scores_real/` (PR #22); `docs/LOCAL_LLM_INSTRUCTOR_RUN.md` |
| 11 | 2026-11-23 | Abby | Run 1–3 primary common sample (no outcome values read) | — | Predictor descriptives: Run 3 distributions; Spearman correlations with EPS surprise and Run 2, `code/describe_run3_features.py` | 304 | No | `outputs/run3_feature_distribution.csv`, `outputs/run3_feature_correlations.csv` |
| 12 | 2026-11-23 | Abby | real cohort + dictionary features + Gemma 4 scores (after cutoff), primary sample | CAR[0,1] | Nested Runs 1–3 (§2–5, Amendments 1–5), `code/run_nested_models.py` @ `b697c88` | 304; 191 / 113 | **Yes, once** | `outputs/model_runs.csv`, `model_coefficients.csv`, `run_predictions.csv`, `nested_sample_flow.csv` (`sample = primary`) |
| 13 | 2026-11-23 | Abby | same, all events (robustness) | CAR[0,1] | same | 307; 192 / 115 | **Yes, once** | same files, `all_events` |
| 14 | 2026-11-23 | Abby | same, primary; `guidance_revision` null as its own category (robustness, Amendment 5) | CAR[0,1] | same + `no_prior_guidance` in Run 3 | 335; 214 / 121 | **Yes, once** | same files, `primary_null_category` |
| 15 | 2026-11-23 | Abby | same, primary; all matched calls, no cutoff filter (robustness, Amendment 5) | CAR[0,1] | same, `..._gemma4_all474.csv` | 360; 247 / 113 | **Yes, once** | same files, `primary_all_calls` |
| 16 | 2026-11-23 | Abby | primary common sample | CAR[0,1] | **Exploratory, not pre-specified:** sentiment gap (prepared-remarks minus analyst-question sentiment) with Run 1 controls, in-sample only, `code/exploratory_sentiment_gap.py` | 304 | No | `outputs/exploratory_sentiment_gap.csv` |
| 17 | 2026-11-23 | Abby | cohort, Yahoo prices as of 2026-11-13, French FF5 (CRSP 202609) | — | Amendment 4 check: easy_es's window rebuilt by `code/car_255_robustness.py --mode easy_es`; reproduces committed `car_0_1_pct` for 492 events (max difference < 0.0001 pp) | 492 | No | — |
| 18 | 2026-11-23 | Abby | same | — | Amendment 4 outcome: CAR[0,1] with a true 255-session estimation window (`--mode full`); median shift 0.27 pp, max 2.75, corr 0.997; HPE 16.89 → 17.91 as in the audit | 492 | No | `outputs/q2_2026_car_255.csv` |
| 19 | 2026-11-23 | Abby | as runs 12–15, outcome replaced by run 18 | CAR[0,1], 255-session window | Nested Runs 1–3, all four samples, `run_nested_models.py --outcome-override` | 304 / 307 / 335 / 360 | **Yes, once** | `outputs/robustness_car255/` |
| 20 | 2026-11-24 | Abby | base sample of Amendment 3 (336 primary events) + Gemma 4 v2.0 scores | CAR[0,1] | **Exploratory, not pre-specified (Amendment 6):** each v2.0 question added alone to Run 1 + Run 2; all five as one block, nulls coded 0 plus an indicator. `code/explore_llm_questions.py`. Pipeline check before the v3.0 scores arrive | 304–335 | Yes (already seen in runs 12–19) | `outputs/exploratory_llm_questions/v2.0_gemma4/` |

**Runs 3 and 6–8: rubric checks on invented calls.** Each cell is the number
of labels agreeing with the reference, summed over the five variables plus
`status`.

| Model | Development (12 calls, 72 labels) | Validation (8 calls, 48 labels) | Parse errors | Cost |
|---|---|---|---|---|
| Haiku 5.5 | 65 / 72 | 39 / 48 | 1 of 8 (validation) | $0.002 + $0.001 |
| Sonnet 5.5 | 70 / 72 | 47 / 48 | 0 | $0.044 + $0.028 |

- **Haiku's parse error.** It was on SYN2-V05, the prompt-injection test
  call. Haiku ignored the embedded instruction, as the prompt asks, but wrote
  a sentence before its JSON, so the reply could not be parsed.
- **Sonnet's misses.** Both development disagreements were
  `analyst_concern_focus` 1 vs 2; the one validation disagreement was
  `qa_evasiveness` 1 vs 2.
- **Conclusion.** The results support the proposed Sonnet 5.5 for Run 3. The
  [TEAM] model decision stays open until the team signs off. *(Superseded by
  Amendment 5: the real calls were scored with Gemma 4 by the course lead.)*

**Runs 4–5 results.** These come from the same script execution. The script
was tested only on invented data before this run.

- **In-sample, primary sample:**
  - R² is 0.036 and adjusted R² is 0.024.
  - The clustered Wald test that all five slopes are zero gives p = 0.0005,
    with 55 day-0 clusters.
  - EPS surprise: +0.060 pp of CAR[0,1] per 1 pp of surprise (p = 0.027).
  - 52-week price change: +0.0024 per pp (p = 0.022).
  - Beta: −0.95 per unit (p = 0.016).
  - Log market cap: −0.53 (p = 0.11).
  - Price-to-book: +0.030 (p = 0.63).
- **Holdout, primary sample:**
  - The training set has day-0 dates through 2026-07-30; the holdout runs
    from 2026-07-31.
  - Out-of-sample R² is 0.004, RMSE 7.63 pp and MAE 5.44 pp.
  - The MSE gain over the training-mean forecast has a supplementary
    week-block 95% interval of [−2.76, 7.61]. It includes zero, so Run 1 is
    not distinguishable from forecasting the mean.
- **Disclosed limitation:** the holdout spans only **4 calendar weeks of
  day 0**, so the week-block bootstrap resamples only 4 blocks and its
  interval is coarse. The Run 2 vs 1 and Run 3 vs 2 intervals will share
  this limitation.
- **All events (robustness):** the estimates are nearly identical:
  - in-sample R² 0.033 and Wald p = 0.0006;
  - holdout out-of-sample R² 0.0005.

**Runs 12–15: nested Runs 1–3 on real data.** Outcome CAR[0,1]. The
primary sample has 304 events. Training covers day 0 through 2026-07-30
(191 events); the holdout runs from 2026-07-31 (113 events).

| Primary | In-sample R² (adj.) | Block Wald p | Holdout R² | RMSE (pp) | Holdout ΔMSE vs. previous [week-block 95%] | Placebo share ≥ actual |
|---|---|---|---|---|---|---|
| Run 1: fundamentals | 0.030 (0.014) | — | 0.034 | 6.84 | — | — |
| Run 2: + dictionary | 0.075 (0.043) | 0.0001 | 0.001 | 6.96 | −1.56 [−1.64, −1.29] | 0.64 |
| Run 3: + LLM | 0.111 (0.065) | 0.0002 | −0.047 | 7.12 | −2.35 [−2.73, −1.03] | 0.76 |

- **Pre-specified answer: not supported.** In-sample, each language block
  is jointly significant. On the holdout, each one makes predictions
  *worse* than the run before it, and shuffled scores do at least as well
  in 64% and 76% of placebo draws. Neither ΔMSE interval lies above zero.
- **Coefficients** (Run 3, primary, clustered by day 0):
  - `guidance_revision`: +1.59 pp of CAR[0,1] per step, from lowered to
    raised guidance (p = 0.037; +1.05 pp per SD).
  - `one_off_attribution`: −0.79 per step (p = 0.053).
  - `analyst_question_sentiment` is the strongest Run 2 variable (p = 0.002
    in Run 2; 0.059 in Run 3).
  - The 52-week return is negative (p = 0.028).
  - EPS surprise is not significant on this smaller, later sample
    (p = 0.19), unlike Run 1's full sample (runs 4–5).
- **Robustness:**
  - `all_events` matches the primary result.
  - `primary_null_category` (335 events): Run 3 is again worse on the
    holdout (ΔMSE −2.80; placebo 0.80).
  - `primary_all_calls` (360 events, including the 79 pre-cutoff calls):
    Run 3 is not significant in-sample (Wald p = 0.092). Its holdout ΔMSE
    is +0.11, with an interval of [−0.32, 1.63] that includes zero.
- **Disclosed limitation:** the transcript data ends 2026-08-07, so the
  holdout spans only **2 calendar weeks** of day 0. The week-block bootstrap
  therefore resamples 2 blocks, and its intervals are too narrow to trust
  on their own. The placebo shares are the steadier evidence, and they
  agree.
- **Run 16, exploratory:** the sentiment gap has a Spearman correlation of
  −0.04 with CAR[0,1]. With Run 1 controls it is −0.25 pp per SD
  [−1.11, 0.61], p = 0.57. There is no sign of an effect.

**Run 20, exploratory (Amendment 6).** Same 336-event base sample, with the
training set through 2026-07-30 and a 121-event holdout. Each v2.0 question
was added alone to Run 1 + Run 2:

| Question | n | Coef. (pp per step) | p | BH q | Holdout ΔMSE | Placebo share |
|---|---|---|---|---|---|---|
| `guidance_revision` | 304 | +1.75 | 0.006 | 0.031 | +1.66 | 0.004 |
| `one_off_attribution` | 335 | −1.02 | 0.026 | 0.064 | +0.11 | 0.23 |
| `analyst_concern_focus` | 335 | −1.22 | 0.053 | 0.089 | −1.65 | 0.95 |
| `qa_evasiveness` | 335 | −0.32 | 0.54 | 0.68 | −0.05 | 0.51 |
| `guidance_specificity` | 335 | +0.29 | 0.91 | 0.91 | −2.03 | 0.93 |

- **Check:** the all-five block (null coded 0 plus an indicator, 335
  events) gives ΔMSE −2.80 and placebo 0.81, the same as run 14
  (`primary_null_category`). That run used separate code.
- **Reading:** `guidance_revision` alone improves the holdout, and almost no
  shuffled draw does as well. In Run 3 it was diluted by four weaker
  variables. This is not an independent discovery. Runs 12–19 had already
  shown it as the strongest variable on the same holdout, so it is a lead
  to test on new data, not a result.

### Amendments

**Amendment 1 · 2026-11-22 · Abby · written before any real-data model fit.**
Freezes §1–7 for Run 1 and settles the [TEAM] items that Run 1 needs.

- **Minimum size:** the proposed rule is adopted. Fewer than 50
  complete-case events means the results are exploratory.
- **Winsorizing:** the proposed rule is adopted. `eps_surprise_pct` and
  `price_to_book` are winsorized at the 1st and 99th percentiles of the
  estimation sample: the full complete-case sample in-sample, and the
  training set for the holdout, with the training bounds applied to the
  holdout. No other variable is winsorized, including `return_52w_pct`.
- **Column mapping (§4 → `outputs/q2_2026_cohort.csv`):**
  - `price_change_52w_pct` → `return_52w_pct`.
  - `beta` → `beta_252d`. §4 says "from Yahoo", but the cohort's beta is
    rebuilt from 252 sessions of daily stock and SPY returns ending on day −1
    (`docs/GUS_DATA_DICTIONARY.md:113`). That is a point-in-time measure,
    which Yahoo's snapshot is not, so we use it.
- **Run 1 now, nested comparison later:** Runs 2–3 are not available yet.
  1. Run 1 is fit and its holdout evaluated now, on the Run 1 complete-case
     sample. Primary: `primary_timing_sample == True`. Robustness: all events.
  2. When Runs 2–3 exist, all three runs are refit on their common
     complete-case sample, as in §2, and evaluated on that sample's holdout.
     That refit gives the nested comparison.
  3. Both sets of Run 1 numbers are reported, each labeled with its sample.
- **Run 1 inference (supplementary):** §5's ΔMSE is defined only between
  runs. For Run 1 alone we also report the week-block bootstrap interval
  (2,000 draws, seed 331) of the MSE gain over the training-mean forecast.
  This is labeled supplementary, not pre-specified.
- **Input file:** `outputs/q2_2026_cohort.csv` as committed in `a6ef269`
  (2026-11-17). It is not rebuilt, because live Yahoo pulls drift (audit A4).
- **Still open, not needed for Run 1:**
  - the Run 3 model choice (Sonnet 5.5 proposed);
  - the ridge robustness check;
  - the Run 3 variable list sign-off.

**Amendment 2 · 2026-11-22 · Abby · transcript coverage (audit CP3 B2).**
Written before any Run 2 or Run 3 result.

- **Source:** option (a) of the audit. On 2026-11-19 the course lead provided
  S&P Capital IQ transcripts through 2026, kept locally in git-ignored
  `restricted_data/`.
  - `code/build_transcript_inputs.py` matches 474 of the 499 cohort events
    to a live earnings call (commit `d2164d9`; coverage in
    `TRANSCRIPT_CHECKPOINT.md`).
  - 21 events were matched by fiscal-period end, because their cohort
    earnings date is an earlier 8-K. Their `day0_session` is checked before
    Runs 2–3.
- **Leakage:** Anthropic publishes a June 2026 training-data cutoff for
  Claude Haiku, Sonnet and Opus 5.5 (models overview, checked 2026-11-19).
  The Run 2–3 sample, and therefore the nested Run 1 refit, is limited to
  calls held after 2026-06-30: 395 of the 474 matched calls. §2's
  "same sample in every run" rule applies to this restricted sample.
- **Route:** transcript text goes only from a team member's own computer,
  through EDSL with remote inference and the remote cache disabled, to
  Anthropic's API under the course's enterprise account, as the course lead
  directed on 2026-11-19. No real transcript is sent until that account's
  API access is confirmed.
- **Rubric check:** before any real call is scored, prompt v2.0 runs
  unchanged on the 8-call synthetic validation set (§4).

**Amendment 3 · 2026-11-22 · Abby · day-0 check and Run 2 features.**
Written before any Run 2 or Run 3 model fit.

- **Day-0 check** (`docs/DAY0_TRANSCRIPT_CHECK.md`,
  `outputs/q2_2026_day0_transcript_check.csv`):
  - 453 matched events have a call consistent with `day0_session`.
  - 21 events have a cohort day 0 before the call, 3–27 trading days early,
    because their timestamp is an earlier 8-K.
  - The 21 are excluded from the Run 2–3 sample and the nested Run 1 refit,
    unless their CAR[0,1] is recomputed at the release that goes with the
    call before Runs 2–3 are scored.
  - Runs 4–5 are not rerun. They include PGR, 1 of 426 primary events, and
    all 21 events in the all-events run, each with the wrong day 0. This is a
    disclosed limitation.
- **Run 2 feature source:**
  - The five §4 Run 2 variables are computed from the Capital IQ
    speaker-tagged components (`code/build_dictionary_features.py`), not by
    parsing speaker labels in the text:
    - prepared remarks: Executives' Presenter Speech;
    - analyst questions: Analysts' Questions;
    - tokens and dictionary flags as in `code/extract_transcript_features.py`.
  - `congratulations_mentioned` follows §4: an analyst question contains
    "congratulations" or "congrats". The older extractor matched
    "congratulations" anywhere in the call.
  - Dictionary: Loughran–McDonald 1993–2025, downloaded 2026-11-22 from the
    SRAF link. SHA-256 `e2d13286…`, the same file as the synthetic
    checkpoint. It is kept in git-ignored `restricted_data/reference/`.
- **Expected common sample:** before LLM missingness, 336 primary events
  (341 all events). The steps:
  1. Run 1 complete: 426 primary events.
  2. Call after the cutoff: 341.
  3. Day 0 consistent: 340.
  4. Run 2 complete: 336.

**Amendment 4 · 2026-11-23 · Abby · estimation-window robustness (audit CP3).**
Adds one robustness row to §6. It does not change the primary analysis.

- **Why:** easy_es expands each event by calendar days, so `estimation_nobs`
  is about 164 trading sessions (median 163), not the nominal 255
  (`docs/GUS_DATA_DICTIONARY.md:78-79`). The auditor's recomputation of 12
  events with a true 255-session window moved CAR[0,1] by at most 1.03 pp
  (HPE 16.89 → 17.91).
- **Robustness row:** recompute CAR[0,1] with a 255-trading-session
  estimation window, using the same Fama–French five factors and gap, and
  rerun Runs 1–3 on that outcome.
- **Labeling:** results are reported as robustness, next to the primary
  table. The primary outcome stays easy_es `car_0_1_pct`.
- **Status:** run 2026-11-23 (run log rows 17–19).
  - **Check:** the code reproduces easy_es's committed `car_0_1_pct` when
    given easy_es's own window.
  - **Primary sample, 255-session window:** the conclusion is unchanged.
    - In-sample R² goes 0.027 → 0.071 → 0.111, with block Wald p = 0.0002
      and 0.0001.
    - Holdout R² goes 0.031 → −0.002 → −0.043, with placebo shares 0.65 and
      0.70.
    - `guidance_revision` is +1.65 per step (p = 0.032).
  - **One exception:** the all-calls row (360 events, which includes the 79
    pre-cutoff calls). There, Run 3 vs. 2 has a ΔMSE interval of
    [0.05, 1.94], just above zero. It is not convincing evidence:
    - the interval comes from 2 bootstrap weeks;
    - the placebo share is 0.12;
    - the in-sample Wald p is 0.062;
    - the sample includes calls inside the training window;
    - the same row on the primary outcome was not supported (run 15).

**Amendment 5 · 2026-11-23 · Abby, with Cammy's sign-off · Run 3 scores.**
Adopted before any Run 2 or Run 3 model fit. No outcome value had been read
for the Run 2–3 sample.

- **Run 3 scores:** Prof. Bowen's local run (run log row 10), replacing the
  proposed Claude Sonnet 5.5.
  - The model was Gemma 4 26B-A4B-it.
  - The enterprise API route in Amendment 2 was not used.
  - No transcript was sent to any outside service.
- **Rubric check on Gemma** (§4, Amendment 2): it was run. On the 8-call
  synthetic validation set, all 8 calls agree with the reference on every
  field. The 12-call development set parsed fully, with one disagreement
  (`docs/LOCAL_LLM_INSTRUCTOR_RUN.md`).
  - These are single temperature-0 runs.
  - No repeated-sampling or second-model reliability check was done on
    real calls.
- **Leakage:** Gemma 4's training data runs to January 2025. This is
  according to NVIDIA's Gemma 4 model card and a Google staff reply on the
  Google AI developer forum, checked 2026-11-23. Google's own model card
  page did not state it in the search results, so the date is reported
  with that caveat.
  - All cohort calls (April–August 2026) are after it.
  - The primary sample stays the 395 calls after 2026-06-30 (Amendment 2),
    so the sample does not change after the scores were seen.
  - Robustness row `primary_all_calls` uses all matched calls
    (`..._gemma4_all474.csv`).
- **Parse failures:** CFG (after the cutoff) and PAYX failed after two
  retries (§4). They are missing and dropped by complete case.
- **`guidance_revision = null`** (31 of 335 primary events: the call has
  nothing to compare with):
  - **primary:** §2's complete-case rule, 304 primary events;
  - **robustness row `primary_null_category`:** null is coded 0, and a
    `no_prior_guidance` indicator is added to the Run 3 block (335 events).
- **`guidance_specificity` barely varies:** 298 of 304 primary events score 2
  (`outputs/run3_feature_distribution.csv`). It stays in Run 3 as
  pre-specified, and its coefficient (resting on 6 events) is reported with
  that caveat.
- **Overlap with Runs 1–2** (Spearman, 304 events): no Run 3 variable
  correlates above 0.31 in absolute value with EPS surprise or with any
  Run 2 variable (`outputs/run3_feature_correlations.csv`).
- **Sentiment gap** (management prepared-remarks sentiment minus
  analyst-question sentiment): not in the official runs. Run 2 already
  contains both of its inputs, so it would be exactly collinear. It is
  reported only afterwards, labeled exploratory.
- **Code:** `code/run_nested_models.py` gains the two robustness variants
  above. The `primary` and `all_events` rows are unchanged from the tested
  pre-specified version.

**Amendment 6 · 2026-11-24 · Abby · exploratory screen of the v3.0 questions.**
Written before any v3.0 score has been received. It does not change §1–7 or
the pre-specified answer (runs 12–19: not supported).

- **Why:** Prof. Bowen offered (email, 2026-11-24) to score up to 20 more
  questions with up to three local models. He advised against reading only
  pre-registered tests. The questions are `docs/LLM_QUESTIONS_V3_DRAFT.md`.
  He will not rerun v2.0, so the 30-call reliability rerun is dropped.
- **Status:** everything below is **exploratory**. It was designed after
  seeing runs 12–19, and the holdout has already been looked at.
- **Analysis** (`code/explore_llm_questions.py`), for each model and for the
  cross-model mean (`consensus`):
  1. **Variation:** value counts and modal share. A modal share above 90%
     is flagged.
  2. **Cross-model agreement:** exact agreement, quadratic-weighted kappa
     and Spearman.
  3. **Overlap:** Spearman with EPS surprise, Run 2 and the v2.0 variables,
     with no outcome read.
  4. **One question at a time:** each question is added to Run 1 + Run 2.
     - Day-0-clustered p, ΔR², holdout ΔMSE against the baseline refit on
       the same events, and a shuffled-score placebo (500 draws, seed 331).
     - Benjamini–Hochberg q within each model.
     - Nulls are dropped. For nullable questions they are also coded 0 plus
       an indicator.
  5. **All questions as one block:** nulls coded 0 plus an indicator. With
     about 20 questions on about 300 events, the in-sample fit is expected
     to overfit.
     - The primary sample has only 21 day-0 clusters. A clustered Wald test
       cannot test as many restrictions as there are clusters minus one.
     - When the block has that many columns, the clustered p is left blank.
       An unclustered F-test p is reported instead, labeled as too
       optimistic.
     - Found on 2026-11-24 in a rehearsal on invented scores, before any
       v3.0 score was received. The 20-question block gave clustered p of
       0.0000 or 1.0000 on random data.
- **Sample:** the base sample of Amendment 3 (336 primary events). The
  holdout split date (day 0 through 2026-07-30) is fixed once on that sample.
- **Validation:** each returned value is checked against the v3.0 rubric. A
  file with a value outside the rubric, or a null where the rubric has none,
  is rejected and not analysed.
- **Reporting:**
  - The results are listed apart from the pre-specified answer.
  - Each one is described as a lead, with its BH q-value and placebo share.
  - With 20 questions × 3 models, about 3 p-values below 0.05 are expected
    by chance alone.
  - A question counts as a lead only if it is consistent across models and
    holds up on the holdout. One significant in-sample coefficient is not
    enough.
- **Lead rule** (Abby and Michelle, 2026-11-24, fixed before any v3.0 score
  was received). A model's question is a lead only if all three hold:
  1. its coefficient has the same sign for at least 2 of the 3 models (the
     consensus row is not counted);
  2. its Benjamini–Hochberg q within that model is below 0.10;
  3. its holdout ΔMSE is above 0, with a placebo share below 0.05.

  `dashboard/exploratory.py` applies this rule. With only one model the
  direction check cannot pass, so run 20 has no leads by construction.
