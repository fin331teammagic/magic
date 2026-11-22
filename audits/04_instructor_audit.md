# Instructor audit: Team Magic, Checkpoint 3

**Repo:** gum327/magic · **Audited commit:** `a270551` (2026-11-17, `main`, merge of PR #14) · **Seeds:** 2 (post-earnings drift) and 7 (analyst calls), as adapted in `PROPOSAL.md`: earnings-call language and post-earnings returns · **CP2 audit:** `audits/02_instructor_audit.md` (commit `3372c54`)

> Note from your human teacher: This review is generated with minimal supervision from Opus 5.5-high. It is thorough, but can be too generous at times and doesn't know my taste for what is "good". Grades it and I would assign are correlated, but noisy, ok? If you want additional feedback from _me_, you need to find me before/after/during class or during office hours for a guaranteed speedy reply. I will try to respond to emails and issues, but can not respond to student inquiries around the clock across the final weeks of class. Response times will be unpredictable, though during Thanksgiving week, I will do my best to respond quickly virtually, as in person options will be nil.

## Summary

`main` now holds the real Q2 2026 cohort, and its pieces reproduce.
- I reran the CAR[0,1] event study for all 499 events. Same 492 complete and 7 dropped, and every CAR within 2e-5 pp.
- My own Fama–French 5 regressions reproduce CAR[0,1] for 12 randomly drawn events to 1e-5 pp.
- The dashboard launches and shows the real cohort.
- `specs_tried.md` (on an unmerged branch) is a careful pre-specification, and it handles CP2's inference point well.

But there are still **no results on real data**. No Run 1, 2 or 3 model has been fit on the cohort. Every model table on the dashboard is synthetic (B1). Your own pre-specification says the licensed transcripts don't cover the cohort's calls, which blocks Runs 2–3 as designed (B2). There is no live dashboard URL yet (B3).

## Follow-up on your Checkpoint 2 audit

Response file: not found. The statuses below come from the repo itself.

| CP2 finding | Status | Evidence |
|---|---|---|
| A1 · `main` doesn't contain all of your work | fixed | PRs #5, #8, #9, #10, #11 and #14 are merged. `main` now has the cohort code (`code/gus_collect.py`, `gus_event_data.py`, `build_cohort_dataset.py`) and outputs, and they reproduce (below). Three newer branches are unmerged again (B4) |
| A2 · No `specs_tried.md` | fixed | Fixed on unmerged branch `abby/specs-tried` (`ebb0882`, Nov 19). The pre-specification is dated before any real-data model ("No model has been fit on real data"), with a run log (§8). It must be merged to `main` to count in the final repo |
| A3 · Inference with overlapping windows | fixed | Same branch, §5 "Inference for correlated holdout errors (A3)": a week-block bootstrap (2,000 draws, seed 331, "supported" only if the 95% interval is above zero) and a shuffled-score placebo, fixed before evaluation. The interval itself comes when the holdout is run |
| A4 · Live pulls drift; versions not pinned | unaddressed | Pins exist only on unmerged `michelle-pins-and-specs` (`468ec02`: exact `requirements.txt`, `requirements-lock.txt`, `.python-version`). `main`'s `requirements.txt` is still unpinned. Raw pulls are cached in `data/raw/` but git-ignored (`.gitignore:23-24`), so a fresh clone re-downloads. Rerun on 2026-11-22: `q2_2026_financial_features.csv` changed for 2 of 499 events (PSKY: 6 features now missing; SNDK: `log_market_cap` 25.81 → 23.73, `price_to_book` 15.85 → 1.98, `avg_daily_volume_63d` ×8), and `beta_252d` moved in its 6th decimal for 299 events |
| A5 · Forward-window off-by-one | unaddressed | `code/pead_pipeline.py:246-248` is unchanged since CP2 (`start = event_position`, `residuals.iloc[start:end]`), and no test checks the window start. The branch's `specs_tried.md` §6 says windows will be "sliced by date (A5)", which is a plan, not a fix |

**3 of 5 fixed, 2 still open.**

## Checkpoint 3 checks

| Check | Result |
|---|---|
| Reruns from scratch (full sample) | ⚠️ the cohort steps rerun (117/117 tests pass; event study and features reproduce, with Yahoo drift). No model run exists to rerun (B1) |
| Inputs have provenance | ✅ `q2_2026_feature_provenance.csv` (6,986 rows: source field, period end, known-by date), `retrieved_at_utc` on every row, French factor vintage (CRSP 202609) |
| Keys unique, merges validated | ✅ `build_cohort_dataset.py` checks unique `event_id` and identical event sets, and merges with `validate="one_to_one"` on all three keys |
| No look-ahead / survivorship | ✅ dated 2026-06-30 roster; features dated before day 0 with status flags (`missing_not_point_in_time`, `observed_consensus_not_pit`). ⚠️ Yahoo revises history (see A4) |
| LLM leakage handled | n/a so far: no LLM scores on real calls. The branch's §4 plans the model ID, cutoff check and a no-outside-information prompt |
| `specs_tried.md` complete | ⚠️ thorough, but only on an unmerged branch (A2, B4) |
| Magnitudes discussed | ❌ no real-data estimates yet (B1) |
| Hand checks | ✅ 117 unit tests on fixtures with known answers. The auditor's FF5 recomputation is below |
| Threats to validity | ✅ STATUS and the dashboard's limitations tab: consensus not point-in-time, timestamp checks, rights, cutoff ≠ absence |
| Every number traces to `outputs/` | ⚠️ the README's question and primary outcome (20-session drift) don't match the analysis plan's (CAR[0,1]) (B5) |
| Dashboard matches `outputs/` | ✅ "Median CAR[0,1] −0.26%" over 463 events = the `primary_timing_sample` median in `q2_2026_cohort.csv` (−0.26, n = 463) |

Steps not rerun by design: `code/gus_collect.py manifest` (SEC EDGAR plus Yahoo earnings dates) and the pilot `code/pead_pipeline.py` (Yahoo earnings-date pages). The audit makes no SEC requests, and doesn't use Yahoo's earnings-date pages. I started from your committed `inputs/q2_2026_events.csv`. These are not counted against you.

## Getting ready for Dec 1

Presentations run only from URLs, with a hard cutoff at 9 minutes (10:45 section) or 10 minutes (12:10 section). Put your URL(s) in column G of the Team Projects sheet.

| Check | Result |
|---|---|
| Dashboard launches from a clean clone | ✅ `streamlit run dashboard/pead_app.py --server.headless true --server.port 8600` on a clean export of `a270551`: `/_stcore/health` returned `ok` after 2 s. A headless browser clicked all 7 tabs, with no exceptions on the page or in the log |
| Dashboard shows the v1 numbers from `outputs/` | ⚠️ the cohort tabs read `outputs/q2_2026_cohort.csv` (`dashboard/data_registry.py:90`) and match it. Every model tab is labeled "synthetic" (`synthetic_model_runs.csv`, `synthetic_model_coefficients.csv`, `synthetic_run_predictions.csv`) because no real model output exists (B1) |
| README links the live URL(s) | ❌ no `streamlit.app` (or other) URL in `README.md`, or anywhere on any branch (B3) |

**Core story for 9–10 minutes:** the question; the dated cohort (499 events, how day 0 is set); the CAR[0,1] distribution; then Run 1 vs Run 2 vs Run 3 on whatever real sample you have, with the pre-specified bootstrap. The transcript-rights history is one slide at most.

## What holds up

- **The event study reproduces.** `python code/gus_collect.py event-study --as-of 2026-11-13` (215 s) gave the same status for every event (492 `complete`, 7 `dropped_by_package`). The largest CAR[0,1] difference from the committed file is 1.8e-5 pp, which is Yahoo drift.
- **Independent recomputation.** My own code reads yfinance adjusted closes and the French FF5 daily file (CRSP 202609, as you record), and fits OLS on the same effective estimation window. It reproduces `car_0_1_pct` for AAPL plus 11 random events (seed 331) to at most 7e-6 pp. For example, AAPL is −9.6263, HPE +16.8866 and NTAP +24.7693.
- **You found easy_es's window quirk yourselves.** `docs/GUS_DATA_DICTIONARY.md:78-79` explains that easy_es expands events by calendar days, so `estimation_nobs` is about 164 rather than 255. I confirmed it (median 163). With a true 255-session window, CAR[0,1] for those 12 events moves by at most 1.03 pp (HPE 16.89 → 17.91). Worth one line in `specs_tried.md` as a robustness row.
- **Merges and missing values.** The cohort join refuses to fill, drop or rename, and every feature carries a status rather than a zero.
- **`specs_tried.md` (branch).** It is a model pre-specification: nested Runs 1–3 on one complete-case sample, clustered SEs by day-0 date, a once-only holdout, and the A3 bootstrap and placebo, all fixed before any real-data fit.

## New findings

### B1 · Blocking · No results on the real cohort yet

**Evidence:** `outputs/` on `a270551` has the cohort (`q2_2026_cohort.csv`, 499 rows) but no model output on it. `model_comparison_metrics.csv` and `holdout_predictions.csv`, which the dashboard expects (`dashboard/data_registry.py:152,170`), don't exist, so it falls back to synthetic fixtures. The only model runs are `outputs/synthetic_model_runs.csv` (3 rows, synthetic). The branch's `specs_tried.md` says "No model has been fit on real data."

**Why it matters:** Checkpoint 3 was v1 on the full sample. Run 1 needs no transcripts: CAR[0,1] and the Run 1 fundamentals are already in the cohort file for 463 primary-timing events. Without it, there's no result to present.

**Fix:** Merge `abby/specs-tried`, freeze §1–7, then run Run 1 on the primary sample: in-sample with clustered SEs, then the holdout once. Write `outputs/model_comparison_metrics.csv` and `outputs/holdout_predictions.csv`, and log the run in §8.

**How to show it's fixed:** Those files exist, with `data_status` not synthetic. I will rerun the script that writes them from `q2_2026_cohort.csv`.

### B2 · Major · Your transcript source doesn't cover the cohort's calls

**Evidence:** `specs_tried.md` §4 (branch `abby/specs-tried`): the licensed dataset "covers calls from 2024-01-05 to 2025-12-19. It does **not** include the July–August 2026 calls in the Q2 2026 cohort." STATUS.md:118 records that uploading licensed transcripts to an AI is currently prohibited.

**Why it matters:** Runs 2 and 3 are the project's contribution. As specified, they can't be run on the cohort. Changing the cohort to 2024–2025 would also bring back the LLM-leakage problem you designed around (those calls are before current models' cutoffs).

**Fix:** Decide now, and log it in `specs_tried.md` §8 as an amendment before any Run 2/3 result:
- (a) a permitted 2026 transcript source, with written rights;
- (b) a 2024–2025 cohort with a masked-name or post-cutoff leakage check;
- or (c) report Run 1 as the result, and Runs 2–3 as a feasibility demonstration on the synthetic set, labeled as such.

**How to show it's fixed:** The amendment exists, dated before the result it governs.

### B3 · Major · No live dashboard URL

**Evidence:** `git grep -iE 'streamlit\.app|github\.io'` finds nothing on `a270551` or on any branch. The README only gives `streamlit run dashboard/pead_app.py`. CP2 noted the same thing.

**Why it matters:** Presentations run only from URLs. The README is required to link the dashboard.

**Fix:** Deploy `dashboard/pead_app.py` from `main` on Streamlit Community Cloud, with Python 3.12 set in the app settings (your branch notes easy_es needs pandas < 2.3). Put the URL at the top of the README and in column G of the sheet.

**How to show it's fixed:** The README links the URL, and the app's requirements match the repo's.

### B4 · Minor · CP3 work is on unmerged branches again

**Evidence:** Three branches had later work than `main` at the deadline, none of them merged:
- `abby/specs-tried` (`ebb0882`, Nov 19), with `specs_tried.md`;
- `michelle-pins-and-specs` (`468ec02`, Nov 17), with the pinned requirements and a draft `specs_tried.md`;
- `abby/llm-rubric-v2` (`3d463bc`, Nov 19), with the v2.0 rubric and the EDSL scorer.

The two `specs_tried.md` drafts differ, and the branch version (§4) refers to the other branches' files.

**Fix:** Merge them into `main`, keeping one `specs_tried.md`.

**How to show it's fixed:** `main` contains all three heads.

### B5 · Minor · The README and the analysis plan name different outcomes

**Evidence:** `README.md:3-9` asks whether call language predicts "20-trading-session factor-proxy-adjusted returns", and `README.md:27` calls that the primary outcome. `ANALYSIS_PLAN.md` ("Outcome") and the branch's `specs_tried.md` §3 make CAR[0,1] primary, with the 20-session return secondary. The 20-session outcome isn't computed for the cohort (`q2_2026_cohort.csv` has only `car_0_1_pct`).

**Fix:** Make the README's question and primary outcome match `specs_tried.md`.

**How to show it's fixed:** The README, `ANALYSIS_PLAN.md`, `specs_tried.md` and the dashboard name the same primary outcome.

## How to respond

This audit is `audits/04_instructor_audit.md` in your repo. Fix what you can, then add `audits/05_audit_response.md`, replying to each **B** finding and to each CP2 finding still open (A4, A5): fixed (the commit), disputed (why), or disclosed as a limitation (where).

There's no separate deadline for this response. Keep working through these until your final deliverables are due: the final repo is audited again then.
