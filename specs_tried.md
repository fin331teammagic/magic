# Specifications tried

Team Magic · responds to instructor audit findings A2 and A3
(`audits/02_instructor_audit.md`).

This file fixes the analysis **before any model is fit on real data or the
holdout is evaluated**, then logs every model run in order. Sections 1–7 are
the pre-specification. Once the first real-data run is logged, they are not
edited. Any later change is added as a dated amendment in Section 8, and
results produced after a change are labeled as not pre-specified.

> **Status:** FROZEN 2026-11-22 (Amendment 1). Drafted 2026-11-19. No model had been fit on real data when it was frozen. The only
> runs in `outputs/` use the synthetic 500-call fixture
> (`data_status = synthetic`). Items marked **[TEAM]** need a team decision
> before this section is frozen.

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
