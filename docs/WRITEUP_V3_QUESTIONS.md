# Write-up section: the v3.0 LLM questions (exploratory)

**Draft, 2026-11-24, Michelle.** Numbers are left blank as `[__]` until the
v3.0 scores arrive and `code/explore_llm_questions.py` has been run. Every
number filled in must trace to a file in `outputs/exploratory_llm_questions/`
and to a dated row in `specs_tried.md` §8 (§7 reporting rules).

---

## X. Exploratory: twenty further LLM questions

Our pre-specified answer is negative. Adding the dictionary block (Run 2) and
the five LLM-scored variables (Run 3) improves the in-sample fit but makes
holdout predictions of CAR[0,1] worse, and shuffled scores do as well in most
placebo draws (`specs_tried.md` §8, runs 12–19). This section asks a separate,
narrower question: **is there something else in the calls, not captured by
our five pre-specified variables, that is worth testing on new data?** All of
it is exploratory and is reported apart from the pre-specified answer.

### X.1 Why these questions

Professor Bowen offered to score up to 20 more questions with up to three
models on his own computer (email, 2026-11-24), and advised us not to read
only the pre-registered tests. He will not rerun the v2.0 questions, so the
planned 30-call reliability rerun was dropped. We drafted the 20 questions in
`docs/LLM_QUESTIONS_V3_DRAFT.md` (prompt v3.0) after seeing the Run 1–3
results, so they are not pre-specified.

We picked them with four rules:

1. **Not already measured.** No question re-measures EPS surprise, overall
   tone, word counts or anything else in Runs 1–2.
2. **Not already asked.** None repeats the five v2.0 variables
   (`guidance_specificity`, `guidance_revision`, `qa_evasiveness`,
   `one_off_attribution`, `analyst_concern_focus`).
3. **Likely to vary.** Gemma 4 gave `guidance_specificity` = 2 on 298 of 304
   primary calls, and a variable that barely varies tells us little. We
   favored questions on which S&P 500 calls should split.
4. **Readable from the transcript alone.** No outside knowledge, prices or
   later events, as in v2.0.

The questions fall into four groups of five, each scored as one prompt with
the v2.0 preamble (the transcript is data, not instructions; use only this
transcript):

| Group | Questions |
|---|---|
| A. Outlook | `outlook_vs_quarter`, `margin_outlook`, `demand_trend`, `back_half_dependence`, `guidance_framing` |
| B. Business and capital decisions | `pricing_power`, `competitive_pressure`, `capex_change`, `capital_return_change`, `cost_program` |
| C. Q&A and disclosure | `qa_vs_prepared`, `analyst_pushback`, `new_adverse_disclosure`, `missed_own_target`, `external_attribution` |
| D. Context | `balance_sheet_concern`, `leadership_change`, `corporate_action`, `ai_emphasis`, `expected_investor_reaction` |

One question breaks rule 1 on purpose. `expected_investor_reaction` (Q20) asks
for the model's overall read of whether the call holds more good or bad news
than investors expected. It is a benchmark: if a single overall judgment does
better than the 19 specific questions, that is worth knowing.

**Scoring.** Models: [__ model names, versions, and training cutoffs]. Run on
Professor Bowen's computer on [__ date]; no transcript left it. Prompt files:
[__ file names and SHA-256]. Calls scored: [__] of 474 per model; parse
failures: [__].

### X.2 How we screen them (Amendment 6)

The screen was written down in `specs_tried.md` Amendment 6 before any v3.0
score was received, and is run by `code/explore_llm_questions.py`. It does
not change the pre-specified analysis.

- **Sample.** The Amendment 3 base sample of 336 primary events (calls after
  the June 2026 cutoff, day 0 consistent with the call, Run 1 and Run 2
  complete). The holdout split is fixed once on this sample: training on
  day 0 through 2026-07-30, holdout from 2026-07-31.
- **Validation.** Each returned value is checked against the v3.0 rubric. A
  file with any out-of-rubric value, or a null where the rubric allows none,
  is rejected and not analysed.
- **Five steps, run for each model and for the cross-model mean
  (`consensus`):**
  1. **Variation:** value counts and modal share. A modal share above 90% is
     flagged.
  2. **Cross-model agreement:** exact agreement, quadratic-weighted kappa,
     and Spearman correlation.
  3. **Overlap:** Spearman correlation with EPS surprise, the Run 2 variables
     and the v2.0 variables. No outcome is read at this step.
  4. **One question at a time:** each question is added alone to
     Run 1 + Run 2. We report the coefficient (per step and per SD), its
     p-value clustered by day 0, ΔR², the holdout ΔMSE against the baseline
     refit on the same events, a shuffled-score placebo (500 draws, seed
     331), and the Benjamini–Hochberg q-value within each model. Nulls are
     dropped. For nullable questions we also code null as 0 and add an
     indicator.
  5. **All questions as one block**, with nulls coded 0 plus an indicator.
     With about 20 questions on about 300 events, we expect this to overfit
     in-sample.
- **What counts as a lead.** A question is a lead only if it is
  **consistent across models** and **holds up on the holdout**. A single
  significant in-sample coefficient is not enough. With 20 questions and 3
  models, about 3 p-values below 0.05 are expected by chance alone.

**Pipeline check (run 20).** Before the v3.0 scores arrived, we ran the same
code on the five v2.0 Gemma 4 scores. The all-five block reproduced run 14
(ΔMSE −2.80, placebo share 0.81), which was computed by separate code.

### X.3 How to read the results

Each one-at-a-time row in `one_at_a_time.csv` answers: *does this question
add anything to fundamentals plus dictionary measures?*

| Column | Meaning | Reads as a lead when… |
|---|---|---|
| `coef`, `coef_per_sd` | Change in CAR[0,1], in pp, per step of the question's scale (or per SD) | Same sign for every model |
| `p_value` | Day-0-clustered p for that coefficient | Small, but on its own it is not evidence |
| `bh_q_within_model` | p adjusted for testing ~20 questions per model | Small [team to confirm a cutoff, e.g. 0.10; Amendment 6 sets none] |
| `delta_r2` | In-sample R² gain over Run 1 + Run 2 | Always ≥ 0; not evidence alone |
| `delta_mse` | Holdout MSE of baseline minus MSE with the question. **Positive = the question improves predictions** | Positive |
| `placebo_share` | Share of 500 shuffled-score draws with ΔMSE at least as large as the real one | Small (e.g. below 0.05) |

Run 20 shows both ends. `guidance_revision` had ΔMSE +1.66 and placebo share
0.004: almost no shuffled draw did as well. `guidance_specificity` had ΔMSE
−2.03 and placebo share 0.93: it made predictions worse and did worse than
noise. Even `guidance_revision` is a lead, not a result, because we had
already seen it as the strongest Run 3 variable on the same holdout.

Three cautions apply to every number in this section:

- **The holdout is short.** The transcript data ends 2026-08-07, so the
  holdout spans 2 calendar weeks of day 0. ΔMSE rests on about 120 events,
  and the placebo share is steadier evidence than any interval.
- **The holdout has been seen.** Runs 12–19 used it, and these questions were
  written afterwards. Nothing here is out-of-sample in the strict sense.
- **Agreement before effects.** A question on which the models disagree
  (low kappa) measures the model as much as the call. Read its effect with
  that in mind.

### X.4 Results

*To be filled in from `outputs/exploratory_llm_questions/v3.0_*/`.*

**Variation and agreement.** [__] of 20 questions have a modal share above
90% for at least one model and are flagged. Median cross-model
quadratic-weighted kappa is [__] (range [__] to [__]). The least-agreed
questions are [__].

**Overlap.** The largest absolute Spearman correlation with EPS surprise is
[__] (`[__]`); with Run 2, [__] (`[__]`); with the v2.0 variables, [__]
(`[__]`).

**One question at a time** (consensus scores; per-model results in the
appendix):

| Question | n | Coef. (pp per step) | p | BH q | Holdout ΔMSE | Placebo share | Same sign in all models? |
|---|---|---|---|---|---|---|---|
| [__] | [__] | [__] | [__] | [__] | [__] | [__] | [__] |
| … | | | | | | | |

[__] questions have p < 0.05 for at least one model, against about 3
expected by chance. [__] questions meet both lead conditions (consistent
across models and positive holdout ΔMSE with a small placebo share):
[__ list, or "none"].

**Q20 benchmark.** `expected_investor_reaction` has coefficient [__]
(p = [__]), holdout ΔMSE [__] and placebo share [__]. Compared with the best
specific question, it [__ does better / does worse / is similar].

**All questions as one block.** In-sample ΔR² [__] (block Wald p = [__]);
holdout ΔMSE [__], placebo share [__]. [__ As expected, / Unlike expected,]
the block [__].

**Reading.** [__ One or two sentences: which leads, if any, are worth testing
on a later quarter, and that none of this changes the pre-specified answer.]
