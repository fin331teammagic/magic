# Write-up section: the v3.0 LLM questions (exploratory)

**Draft 2026-11-24, numbers filled in 2026-11-25, Michelle.** Numbers come
from runs 21–23 (`specs_tried.md` §8). Every number must trace to a file in
`outputs/exploratory_llm_questions/`
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

The questions fall into four groups of five. The draft planned one prompt per
group. Professor Bowen instead asked all 20 in a single prompt with the v2.0
preamble (the transcript is data, not instructions; use only this
transcript), because most of the run time goes into the models' reasoning,
so four prompts would cost about four times as much. On 20 synthetic calls,
Gemma's answers from one 20-question prompt and from two 10-question prompts
agreed on 93% of the 400 answers (`docs/LOCAL_LLM_V3_RUN.md`).

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

**Scoring (run 21).** Three open-weight models from three different makers:

| Model | Weights file | Training cutoff |
|---|---|---|
| Gemma 4 26B-A4B (Google) | `gemma-4-26B-A4B-it-UD-Q6_K_XL.gguf` | January 2025 (Google's model card) |
| gpt-oss-20b (OpenAI) | `gpt-oss-20b-MXFP4.gguf` | June 2024 (OpenAI's model card) |
| Qwen3.5-27B (Alibaba) | `Qwen3.5-27B-UD-Q5_K_XL.gguf` | Not stated; weights published 2026-02-24, before the first Q2 2026 call |

All three were trained before the calls they score. They ran on Professor
Bowen's computer from 2026-11-24 21:35 to 2026-11-25 09:48 UTC, and no
transcript left it. The setup: llama.cpp `b12651`; EDSL 1.0.9, local only;
temperature 0, with up to two retries at 0.7 for replies that did not
parse; `max_tokens` 16,384; reasoning capped at 12,288 tokens. Each model
scored each call once.
Prompt file: `prompts/transcript_llm_scores_v3.0_all.txt` (version
`v3.0-all`), SHA-256
`c92479102951cc43559428386e8fabb7f97ddcb955f63c861fc39ecca23d841f`, which
matches every scored row. Calls scored: 474 of 474 for Gemma 4 and Qwen3.5,
473 of 474 for gpt-oss. The screen uses the 395 calls after the training
cutoff. Parse failures: none for Gemma 4 or Qwen3.5. For gpt-oss, 28 replies
first put a null where the rubric allows none and were scored again, and
one call (SHW_2026-06-30) still failed after two retries, so it is recorded
as missing rather than imputed.

Two features of the run affect how to read the scores. Gemma reached the
reasoning cap on 206 of 474 calls and Qwen on 182. The cap cut short
re-checking that was mostly on judgment items such as `qa_vs_prepared`,
`external_attribution` and `expected_investor_reaction`. The cap does not
seem to work with gpt-oss's chat format, so its long calls relied on
retries instead (`docs/LOCAL_LLM_V3_RUN.md`).

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
- **What counts as a lead** (Amendment 6 lead rule, fixed 2026-11-24 before
  any v3.0 score was received).
  1. **Passes for a model:** a question passes for a model if both hold:
     - its **Benjamini–Hochberg q within that model is below 0.10**;
     - its **holdout ΔMSE is above 0, with a placebo share below 0.05**.
  2. **Lead:** it **passes, with the same coefficient sign, in at least 2 of
     the 3 models**. The consensus row is not counted.

  A rule that required only the same sign in 2 of 3 models would filter
  almost nothing: with three models, two always share a sign. In a rehearsal
  on random invented scores, that weaker rule passed a chance result. The
  rule above passed none.

  A single significant in-sample coefficient is not enough. With 20
  questions and 3 models, about 3 p-values below 0.05 are expected by chance
  alone. The dashboard's exploratory tab (`dashboard/exploratory.py`)
  applies the same rule.

**Pipeline check (run 20).** Before the v3.0 scores arrived, we ran the same
code on the five v2.0 Gemma 4 scores. The all-five block reproduced run 14
(ΔMSE −2.80, placebo share 0.81), which was computed by separate code.

### X.3 How to read the results

Each one-at-a-time row in `one_at_a_time.csv` answers: *does this question
add anything to fundamentals plus dictionary measures?*

| Column | Meaning | Lead rule (Amendment 6) |
|---|---|---|
| `coef`, `coef_per_sd` | Change in CAR[0,1], in pp, per step of the question's scale (or per SD) | Same sign as the other passing model(s) |
| `p_value` | Day-0-clustered p for that coefficient | Not part of the rule; on its own it is not evidence |
| `bh_q_within_model` | p adjusted for testing ~20 questions per model | Below 0.10 |
| `delta_r2` | In-sample R² gain over Run 1 + Run 2 | Not part of the rule; always ≥ 0 |
| `delta_mse` | Holdout MSE of baseline minus MSE with the question. **Positive = the question improves predictions** | Above 0 |
| `placebo_share` | Share of 500 shuffled-score draws with ΔMSE at least as large as the real one | Below 0.05 |

All three conditions must hold for the same model.

Run 20 shows both ends. `guidance_revision` had ΔMSE +1.66 and placebo share
0.004: almost no shuffled draw did as well. `guidance_specificity` had ΔMSE
−2.03 and placebo share 0.93: it made predictions worse and did worse than
noise. Run 20 has only one model, so no question can pass in two models and
it has no leads by construction. Even if it could, `guidance_revision` would be
a lead, not a result, because we had already seen it as the strongest Run 3
variable on the same holdout.

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

Source: run 22 (`outputs/exploratory_llm_questions/v3.0_three_models/`,
`SUMMARY.md`) and run 23 (`outputs/exploratory_llm_questions/v3.0_run3_baseline/`).
Base sample 336 primary events: 215 in training and 121 in the holdout,
in 21 day-0 clusters.

**Variation and agreement.** 6 of 20 questions have a modal share above 90%
for at least one model and are flagged. `qa_vs_prepared` and
`balance_sheet_concern` are flagged in all three models.
`new_adverse_disclosure` is flagged in two (Gemma 4, gpt-oss), and
`analyst_pushback`, `missed_own_target` and `external_attribution` in one
each. No question is over 50% null. The median cross-model quadratic-weighted
kappa, over the 60 question × model-pair cells, is 0.54 (range −0.04 to
0.93). The least-agreed questions, by mean kappa over the three pairs, are
`qa_vs_prepared` (0.10), `external_attribution` (0.22) and
`analyst_pushback` (0.23). Gemma 4 and Qwen3.5 agree with each other most,
and gpt-oss is usually the odd one out.

**Overlap.** Across the three models, the largest absolute Spearman
correlations are:

- with EPS surprise: 0.18 (`outlook_vs_quarter`, Gemma 4, ρ = −0.18);
- with Run 2: 0.29 (`ai_emphasis` with the uncertainty-word proportion,
  gpt-oss, ρ = −0.29);
- with the v2.0 variables: 0.46 (`expected_investor_reaction` with
  `guidance_revision`, Gemma 4).

Only Q20 overlaps much with what we already had, and Q20 is the planned
overall read.

**One question at a time.** The table shows each question and model with
p < 0.05 or a pass, plus the gpt-oss rows for the two leads. The full 80 rows,
including consensus, are in `one_at_a_time.csv` and `SUMMARY.md`. The
baseline is Run 1 + Run 2, and nulls are dropped.

| Question | Model | n | Coef. (pp per step) | p | BH q | Holdout ΔMSE | Placebo share | Passes for this model? | Models passing, same sign | Lead? |
|---|---|---|---|---|---|---|---|---|---|---|
| `expected_investor_reaction` | Gemma 4 | 336 | +2.61 | <0.001 | <0.001 | +2.30 | 0.000 | yes | 2 | **yes** |
| `expected_investor_reaction` | Qwen3.5 | 336 | +2.67 | <0.001 | <0.001 | +3.67 | 0.000 | yes | 2 | **yes** |
| `expected_investor_reaction` | gpt-oss | 335 | +1.71 | 0.080 | 0.399 | +0.08 | 0.294 | no | 2 | — |
| `analyst_pushback` | Gemma 4 | 336 | −1.85 | 0.010 | 0.089 | +1.29 | 0.012 | yes | 2 | **yes** |
| `analyst_pushback` | Qwen3.5 | 336 | −1.73 | 0.003 | 0.023 | +1.38 | 0.010 | yes | 2 | **yes** |
| `analyst_pushback` | gpt-oss | 335 | +0.36 | 0.565 | 0.897 | −0.05 | 0.540 | no | 0 | — |
| `missed_own_target` | Qwen3.5 | 336 | −2.99 | 0.001 | 0.011 | +1.28 | 0.004 | yes | 1 | no |
| `margin_outlook` | Qwen3.5 | 318 | +1.62 | 0.018 | 0.088 | +1.40 | 0.010 | yes | 1 | no |
| `guidance_framing` | gpt-oss | 335 | −2.18 | 0.005 | 0.105 | +1.27 | 0.010 | no (q) | 0 | no |
| `guidance_framing` | Gemma 4 | 336 | −1.77 | 0.013 | 0.089 | −0.55 | 0.792 | no | 0 | no |
| `demand_trend` | Gemma 4 | 336 | +1.25 | 0.022 | 0.111 | +0.45 | 0.078 | no | 0 | no |
| `demand_trend` | Qwen3.5 | 335 | +1.13 | 0.034 | 0.103 | −0.13 | 0.604 | no | 0 | no |
| `demand_trend` | gpt-oss | 333 | +1.61 | 0.042 | 0.312 | −2.02 | 0.988 | no | 0 | no |
| `outlook_vs_quarter` | Qwen3.5 | 336 | +1.60 | 0.029 | 0.103 | +0.62 | 0.058 | no | 0 | no |
| `capital_return_change` | Qwen3.5 | 336 | +0.87 | 0.036 | 0.103 | +0.07 | 0.276 | no | 0 | no |
| `qa_vs_prepared` | gpt-oss | 335 | +2.08 | 0.047 | 0.312 | +0.07 | 0.330 | no | 0 | no |

9 questions have p < 0.05 for at least one model: 14 of the 60
question × model rows, against about 3 expected by chance. Under the
Amendment 6 lead rule (BH q < 0.10 and holdout ΔMSE > 0 with placebo share
< 0.05, passed with the same sign in at least 2 of 3 models), **2 questions
are leads**:

- `expected_investor_reaction`: passes for Gemma 4 and Qwen3.5 (and for the
  consensus, which is not counted). It is +1.3 to +1.6 pp per SD.
- `analyst_pushback`: passes for Gemma 4 and Qwen3.5 (and the consensus).
  It is −1.0 to −1.1 pp per SD. More pushback from analysts goes with a
  lower CAR[0,1].

`missed_own_target` and `margin_outlook` pass for Qwen3.5 alone, so they are
not leads. `guidance_framing` improves the gpt-oss holdout but misses the q
threshold (0.105), and in Gemma 4 it makes the holdout worse.

**Q20 benchmark.** `expected_investor_reaction` has coefficient +2.61 pp per
step in Gemma 4 and +2.67 in Qwen3.5 (both p < 0.001). Its holdout ΔMSE is
+2.30 and +3.67, with placebo share 0.000 in both. In gpt-oss it is +1.71
(p = 0.080), ΔMSE +0.08 and placebo share 0.294. Compared with the best
specific question, it does better in Gemma 4 (ΔMSE +2.30 vs +1.29), Qwen3.5
(+3.67 vs +1.40) and the consensus (+3.17 vs +1.59), and worse in gpt-oss
(+0.08 vs +1.27). It is also the question that overlaps most with v2.0
`guidance_revision` (ρ = 0.46 in Gemma 4, 0.44 in Qwen3.5), the strongest
v2.0 variable in run 20. Part of what it picks up is probably that same
signal.

**All questions as one block** (nulls coded 0 plus an indicator, 22–23
added columns). In-sample ΔR² is 0.087 to 0.106. The day-0-clustered block
Wald p cannot be computed, because the block has more columns than the 21
day-0 clusters allow. The unclustered F p is 0.026 to 0.098, which is too
optimistic. Holdout ΔMSE is −2.16 (Gemma 4), −12.40 (gpt-oss), −2.78
(Qwen3.5) and −1.55 (consensus), with placebo shares from 0.13 to 0.97. As
expected, the block overfits: it raises in-sample fit and makes holdout
predictions worse in every model.

**Robustness: the v2.0 variables in the baseline (run 23).** On the 304
events with Run 1–3 complete, we add the five v2.0 Gemma 4 variables to the
baseline. Both leads keep their sign and still improve the holdout:

- Q20: +1.8 to +2.9 pp per step, placebo share at most 0.034;
- `analyst_pushback`: −1.7 to −2.8 pp, placebo share 0.000.

Gemma 4's q rises to 0.17 for both questions, though, so only Qwen3.5
passes. Under this baseline neither question meets the 2-of-3 rule.
`analyst_pushback` correlates at most 0.08 in absolute value with any
earlier variable.

**Reading.** Two leads are worth testing on a later quarter.
`analyst_pushback` looks like a new signal: it overlaps with nothing we
already measured. Its agreement is weak, though. The kappa is 0.52 between
Gemma 4 and Qwen3.5, but about 0.1 between gpt-oss and either of them, and
gpt-oss shows no effect. Q20 is the draft's planned exception, an overall
judgment rather than a new specific signal, and it partly re-measures
`guidance_revision`. Both leads rest on the two most similar models. Both
come from a 2-week holdout that we had already seen, and each model scored
each call once. Neither meets the lead rule once the v2.0 variables are in
the baseline. None of this changes the pre-specified answer (runs 12–19:
the LLM-scored variables do not improve holdout predictions of CAR[0,1]).
