# Team Magic: who does what until Dec 1

Updated 2026-11-23 by Abby.

- The repo is now `fin331teammagic/magic`; old `gum327` links redirect.
- PR #17 (the audit fixes) is merged into `main`.
- The audit response is in `audits/05_audit_response.md`.

## Where we are

| Piece | Status | Where |
|---|---|---|
| Run 1 (fundamentals) on the real cohort | Done: in-sample R² 0.036 (Wald p = 0.0005), holdout R² 0.004 | `outputs/model_comparison_metrics.csv`, `specs_tried.md` §8 |
| Pre-specification | Frozen, with Amendments 1–3 | `specs_tried.md` |
| 2026 transcripts matched to the cohort | 474 of 499; 395 after the June 2026 model cutoff | `TRANSCRIPT_CHECKPOINT.md` |
| Run 2 dictionary features | Built (local, no text committed) | `outputs/q2_2026_dictionary_features.csv` |
| Run 3 LLM scores | **Blocked:** needs an enterprise API key (Abby asked Prof. Bowen) | `TRANSCRIPT_CHECKPOINT.md`, bottom |
| Runs 1–3 comparison | Code ready, tested on invented data; runs once the scores exist | `code/run_nested_models.py` |
| Live dashboard (audit B3) | **Live:** https://team-magic-pead.streamlit.app | README |
| Day-0 mismatches (21 events) | Found and excluded from Runs 2–3 | `docs/DAY0_TRANSCRIPT_CHECK.md` |

## Gus

1. ~~Dashboard~~ **Done, 2026-11-23.** Streamlit is allowed in the org and
   the app is live. Optional: delete nothing; the app is in the
   `fin331teammagic` workspace on share.streamlit.io.
2. **Day-0 fix (optional, but it adds events).** For the 21 events in
   `docs/DAY0_TRANSCRIPT_CHECK.md`, the cohort timestamp is an earlier 8-K.
   - Find the 8-K that carries the quarterly earnings release. It is
     usually filed on the call date or the evening before.
   - Rerun the event study for those events.

   If that's done before Runs 2–3 are scored, the events come back in
   (Amendment 3).

## Cammy

Decide these before the transcripts are scored, and record them as an
amendment in `specs_tried.md` §8:

1. **Review Amendments 1–3:**
   - the 50-event minimum;
   - the 1st/99th-percentile caps on EPS surprise and price-to-book;
   - Run 1 reported now and refit later on the common sample;
   - only post-cutoff calls in Runs 2–3;
   - excluding the 21 day-0 mismatches.
2. **The `guidance_revision = null` rule.** Claude returns null when a call
   gives no way to compare with prior guidance. Under the current
   complete-case rule, those calls drop out of all three runs. The
   alternative is to treat null as its own category: 0 plus a
   `no_prior_guidance` indicator.
3. **Run 3 model.** Sonnet 5.5 is proposed. It agreed with 47/48 synthetic
   validation labels vs. 39/48 for Haiku (§8, runs 6–8).
4. **After the scores exist,** own the statistics slides from
   `outputs/model_runs.csv` and `outputs/model_coefficients.csv`.

## Michelle

1. **Look over what PR #17 merged.**
   - Abby's `specs_tried.md` (Nov 19) replaced the Nov 17 draft, because
     the audit asked for one copy.
   - Your version pins are merged.
2. **After Runs 2–3 run,** point the `model_runs`, `model_coefficients` and
   `run_predictions` entries in `dashboard/data_registry.py` at
   `outputs/model_runs.csv`, `outputs/model_coefficients.csv` and
   `outputs/run_predictions.csv`.
3. **Own the dashboard walkthrough** for the presentation.

## Abby

1. Get the enterprise API key with Prof. Bowen.
   - No real transcript has been sent.
   - Abby's personal key was used only on 20 invented calls.
2. Score the 395 calls, then run `code/run_nested_models.py`. The steps are
   at the bottom of `TRANSCRIPT_CHECKPOINT.md`.
3. Finalize `audits/05_audit_response.md` once B3 and the scores are done.

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
| Tue Nov 24 | Cammy's decisions; Gus allows Streamlit in the org |
| Before Thanksgiving | Scores and Runs 1–3, if the API key arrives |
| Mon Dec 1 | Presentation from the live URL (9–10 minutes) |
