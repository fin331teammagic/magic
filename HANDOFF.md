# Team Magic: who does what until Dec 1

Updated 2026-11-23 by Abby.

- The repo is now `fin331teammagic/magic`; old `gum327` links redirect.
- PR #17 (the audit fixes) is merged into `main`.
- The audit response is in `audits/05_audit_response.md`.

## Where we are

| Piece | Status | Where |
|---|---|---|
| Run 1 (fundamentals) on the real cohort | Done: in-sample R² 0.036 (Wald p = 0.0005), holdout R² 0.004 | `outputs/model_comparison_metrics.csv`, `specs_tried.md` §8 |
| Pre-specification | Frozen, with Amendments 1–5 | `specs_tried.md` |
| 2026 transcripts matched to the cohort | 474 of 499; 395 after the June 2026 model cutoff | `TRANSCRIPT_CHECKPOINT.md` |
| Run 2 dictionary features | Built (local, no text committed) | `outputs/q2_2026_dictionary_features.csv` |
| Run 3 LLM scores | **Done** by Prof. Bowen on a local model (Gemma 4), merged in PR #22: 394 of 395 parsed | `outputs/llm_scores_real/`, `docs/LOCAL_LLM_INSTRUCTOR_RUN.md` |
| Runs 1–3 comparison | **Done 2026-11-23:** language not supported out of sample (holdout R² 0.034 → 0.001 → −0.047) | `outputs/model_runs.csv`, `specs_tried.md` §8 runs 12–16, dashboard Results tab |
| Live dashboard (audit B3) | **Live:** https://team-magic-pead.streamlit.app | README |
| Day-0 mismatches (21 events) | Found and excluded from Runs 2–3 | `docs/DAY0_TRANSCRIPT_CHECK.md` |

## Gus

1. ~~Dashboard~~ **Done, 2026-11-23.** Streamlit is allowed in the org and
   the app is live. Optional: delete nothing; the app is in the
   `fin331teammagic` workspace on share.streamlit.io.
2. ~~Day-0 fix~~ **No longer needed.** Runs 2–3 have run, and the 21 events
   in `docs/DAY0_TRANSCRIPT_CHECK.md` stay excluded and disclosed
   (Amendment 3). Fixing them now would change the sample after results.
3. **Presentation:** the cohort slide (499 events, how day 0 is set, the
   CAR[0,1] distribution).

## Cammy

1. ~~Amendment 5 decisions~~ **Done 2026-11-23** (Gemma 4 scores; drop the 31
   guidance nulls for the primary result; sentiment gap only as exploratory).
2. **Own the statistics slides** from `outputs/model_runs.csv`,
   `outputs/model_coefficients.csv` and `specs_tried.md` §8, runs 12–16. The
   story:
   - in-sample, language looks significant;
   - out of sample, it makes predictions worse;
   - the placebo agrees;
   - the caveat is a 2-week holdout.

## Michelle

1. ~~Point the dashboard at the real runs~~ **Done**: the Results tab now
   shows Runs 1–3, with a sample picker for the robustness checks.
2. **Own the dashboard walkthrough** for the presentation (Results tab
   first, then Findings for Run 1 on its full sample).

## Abby

1. ~~API key~~ Not needed: Prof. Bowen scored the calls locally (PR #22).
2. ~~Runs 1–3~~ **Done 2026-11-23** (`specs_tried.md` §8, runs 12–16).
3. Presentation outline for Dec 1.

## Rules for everyone

- **Never commit or upload anything from `restricted_data/`** (licensed
  transcripts). **This repo appears to be public.**
- Never paste transcript text into a chat or a web tool.
- Never commit an API key.
- Work on a branch and open a PR; don't commit to `main` directly.
- Set up Python 3.12 from `requirements-lock.txt` (see `README.md`). Run the
  tests with `python -m unittest discover -s tests`.
- Log every model run in `specs_tried.md` §8. The holdout is evaluated
  **once** per run.

## Timeline

| By | What |
|---|---|
| ~~Tue Nov 24~~ | ~~Amendment 5; Runs 1–3~~ done Nov 23 |
| Before Thanksgiving | Results on the dashboard; slides drafted |
| Mon Dec 1 | Presentation from the live URL (9–10 minutes) |
