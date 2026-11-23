# Response to the Checkpoint 3 instructor audit

Team Magic. This responds to `audits/04_instructor_audit.md` (audited commit
`a270551`).

> **Status, updated 2026-11-23.** PR #17 was merged into `main` on
> 2026-11-22 (merge commit `15a054c`), so the commits below are in `main`.
> The repository has moved from `gum327/magic` to `fin331teammagic/magic`,
> and the old links redirect.
>
> Still open:
> - B3: the dashboard deploy is waiting on the organization approving
>   Streamlit;
> - Runs 2–3: waiting on API access under the course's enterprise account.

## Summary

| Finding | Response | Where |
|---|---|---|
| B1 · No real-data results | **Fixed** for Run 1. Runs 2–3 are waiting on transcript scoring | `31df28b` |
| B2 · Transcripts don't cover the cohort | **Fixed** by amendment, option (a). Scoring waits on API access | `971e1a3`, `d2164d9` |
| B3 · No live dashboard URL | **In progress.** Deploy is set up; waiting on the org to allow Streamlit | — |
| B4 · Unmerged branches | **Fixed.** `main` contains all three heads (`ebb0882`, `468ec02`, `3d463bc`) | `15a054c` |
| B5 · README vs. plan outcome | **Fixed** | `a29a1e4` |
| CP2 A4 · Versions not pinned; Yahoo drift | Pins **fixed**. Drift is **disclosed** and contained | `ba726b7`, `971e1a3` |
| CP2 A5 · Forward-window off-by-one | **Fixed** | `5320e8d` |

## B1 · No results on the real cohort: fixed (Run 1)

1. We merged `abby/specs-tried` and froze `specs_tried.md` §1–7 with
   Amendment 1 (`971e1a3`), before any real-data fit. Amendment 1:
   - settles the Run 1 [TEAM] items: the 50-event minimum, and winsorizing
     `eps_surprise_pct` and `price_to_book` at the 1st/99th percentiles of
     the estimation sample;
   - maps the spec's variable names to cohort columns;
   - explains how Run 1 is refit on the common sample once Runs 2–3 exist.
2. `code/run_models.py` implements §2–5 for Run 1:
   - OLS with standard errors clustered by `day0_session`, and a clustered
     Wald test;
   - a 60/40 chronological split moved to a day-0 boundary;
   - one holdout evaluation, on the primary sample and on all events.
   Its tests use an invented cohort with planted coefficients
   (`tests/test_run_models.py`). They ran before the real fit.
3. The outputs, all with `data_status = cohort`:
   - `outputs/model_comparison_metrics.csv`
   - `outputs/holdout_predictions.csv`
   - `outputs/run1_coefficients.csv`
   - `outputs/run1_sample_flow.csv`

   They are logged as runs 4–5 in `specs_tried.md` §8.

**Results.** The primary sample is 426 complete-case events (sample flow in
`run1_sample_flow.csv`).

- **In-sample:**
  - R² is 0.036 and adjusted R² is 0.024.
  - The clustered Wald test that all five slopes are zero gives p = 0.0005,
    with 55 day-0 clusters.
  - EPS surprise: +0.060 pp of CAR[0,1] per pp of surprise (p = 0.027).
  - 52-week price change: +0.0024 per pp (p = 0.022).
  - Beta: −0.95 per unit (p = 0.016).
  - Size and price-to-book are not significant.
- **Holdout** (292 training events and 134 holdout events; holdout day 0
  from 2026-07-31):
  - out-of-sample R² is 0.004, RMSE 7.63 pp and MAE 5.44 pp;
  - the MSE gain over the training-mean forecast has a supplementary
    week-block 95% interval of [−2.76, 7.61].

  So the fundamentals are statistically related to the reaction in-sample
  but add essentially nothing out-of-sample. The all-event robustness run
  is nearly identical.

**Disclosed limitation.** Under the pre-specified 60/40 split, the holdout
spans only 4 calendar weeks of day 0. The week-block bootstrap therefore
resamples 4 blocks, and its intervals are coarse. This will also apply to
the Run 2 vs 1 and Run 3 vs 2 comparisons.

**To rerun:**

```
python code/run_models.py
```

It reads `outputs/q2_2026_cohort.csv` as committed in `a6ef269`.

The dashboard's *Findings* tab now shows real Run 1. It was checked with
Streamlit's `AppTest`, with no exceptions.

## B2 · Transcript coverage: fixed by amendment, option (a)

`specs_tried.md` Amendment 2 (`971e1a3`) records the 2024–2026 S&P Capital
IQ transcripts the course provided on 2026-11-19.

- `code/build_transcript_inputs.py` (`d2164d9`) matches **474 of 499**
  cohort events to a live earnings call.
  - The match file has no transcript text. All licensed files stay in
    git-ignored `restricted_data/`.
  - 21 events matched only by fiscal-period end, because their cohort
    earnings date is an earlier 8-K. Their `day0_session` is checked before
    Runs 2–3.
- **Leakage:** Claude Haiku, Sonnet and Opus 5.5 all have a published June
  2026 training-data cutoff. The Run 2–3 sample, and the nested Run 1 refit,
  is therefore limited to the **395** matched calls held after 2026-06-30.
- **Route:** EDSL runs locally with remote inference and the remote cache
  disabled, and sends directly to Anthropic under the course's enterprise
  account, as you directed.
- **Blocker:** our Claude Console login shows only a personal organization,
  so we have asked you how to get an API key under the enterprise account.
  No real transcript has been sent.
- **Day-0 check** (Amendment 3, `7306976`; `docs/DAY0_TRANSCRIPT_CHECK.md`):
  - 453 matched events have a call consistent with their `day0_session`.
  - 21 have a cohort day 0 that is an earlier 8-K, 3–27 trading days
    before the call. They are excluded from Runs 2–3 unless their CAR is
    recomputed.
  - In Run 1, this affects 1 primary event (PGR). It is disclosed.
- **Run 2 is built; Run 3 is ready.**
  - The five Run 2 dictionary variables are computed locally for all 474
    matched calls from Capital IQ's speaker-tagged components
    (`outputs/q2_2026_dictionary_features.csv`). Nothing was sent anywhere.
  - `code/run_nested_models.py` (`6857eaf`) implements the full nested
    comparison: block Wald tests, the week-block bootstrap of ΔMSE and the
    shuffled-score placebo. Its tests use a planted effect.
  - It runs as soon as the LLM scores exist. The expected common sample is
    336 primary events.
- **Prompt check:** prompt v2.0 has been checked, unchanged, on the 8-call
  synthetic validation set (runs 6–8):
  - Sonnet 5.5 agreed with 47 of 48 reference labels;
  - Haiku 5.5 agreed with 39 of 48, including one parse failure on the
    prompt-injection test call.

## B3 · No live dashboard URL: in progress

The repository now lives in the `fin331teammagic` organization, so a team
member can deploy it with admin rights. The Streamlit app is configured:
- app file `dashboard/pead_app.py`;
- branch `main`;
- Python 3.12, matching `.python-version` and the pinned
  `requirements.txt`;
- address `team-magic-pead.streamlit.app`.

The new organization has GitHub's OAuth app restrictions turned on, so an
organization owner has to approve Streamlit before the deploy can run. When
it is live, the URL goes at the top of the README and in column G of the
sheet.

## B4 · Unmerged branches: fixed

PR #17 (merge commit `15a054c`) brought all three branch heads into `main`:
- `abby/specs-tried` (`ebb0882`);
- `michelle-pins-and-specs` (`468ec02`);
- `abby/llm-rubric-v2`.

There is one `specs_tried.md`: the Nov 19 version. Michelle's Nov 17 draft
is superseded and noted in §8 (run 2).

## B5 · Outcome mismatch: fixed

In `a29a1e4`:
- The README's question and "Primary outcome" now name CAR[0,1], matching
  `ANALYSIS_PLAN.md` and `specs_tried.md` §3.
- The 20-session ETF-proxy return is listed as secondary.
- The dashboard's "How the study works" panel says the same.

## CP2 A4 · Pinned versions and Yahoo drift

- **Pins: fixed.** `ba726b7` merges the exact `requirements.txt`,
  `requirements-lock.txt` and `.python-version` (3.12). All 142 tests pass
  in a fresh environment built from `requirements-lock.txt`.
- **Drift: disclosed and contained.**
  - Run 1 reads the committed `outputs/q2_2026_cohort.csv` (`a6ef269`) and
    never re-pulls Yahoo. Every model result is therefore reproducible from
    the repo.
  - A fresh `gus_collect.py` rebuild can still differ, as you found for
    PSKY and SNDK. This is recorded in `specs_tried.md` Amendment 1.

## CP2 A5 · Forward-window off-by-one: fixed

In `5320e8d`:
- `calculate_factor_proxy_returns` now slices residuals by date:
  `residuals.loc[residuals.index > event_session]`.
- A new test pins the 1- and 5-session windows to the session after the
  reaction (`tests/test_pead_pipeline.py`).
- As you noted, the old code gave the same numbers. The fix removes the
  dependence on returns being exactly one row shorter than prices.

## Other suggestions in the audit

- **The easy_es estimation window** (164 rather than 255 sessions) is added
  as a pre-specified robustness row in `specs_tried.md` Amendment 4. It has
  not been run yet.
