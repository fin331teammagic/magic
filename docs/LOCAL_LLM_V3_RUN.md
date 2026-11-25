# v3.0 questions on the Q2 2026 cohort: instructor's local run (2026-11-24/25)

The instructor scored the cohort's real transcripts with three open-weight models, asking the 20 questions in `docs/LLM_QUESTIONS_V3_DRAFT.md`. The models ran on the instructor's own computer, and the transcript text never left it. The scores are in `outputs/llm_scores_real/`, and the prompt is in `prompts/transcript_llm_scores_v3.0_all.txt`.

## Files

| file (in `outputs/llm_scores_real/`) | rows | usable (parsed, `status` scored) |
|---|---|---|
| `q2_2026_llm_scores_v3.0_gemma4_all474.csv` | 474 | 474 |
| `q2_2026_llm_scores_v3.0_gemma4_after_cutoff395.csv` | 395 | 395 |
| `q2_2026_llm_scores_v3.0_gptoss20b_all474.csv` | 474 | 473 (SHW missing) |
| `q2_2026_llm_scores_v3.0_gptoss20b_after_cutoff395.csv` | 395 | 394 (SHW missing) |
| `q2_2026_llm_scores_v3.0_qwen35_27b_all474.csv` | 474 | 474 |
| `q2_2026_llm_scores_v3.0_qwen35_27b_after_cutoff395.csv` | 395 | 395 |

- The columns are the v2.0 output columns, with the 20 v3.0 variables in place of the five v2.0 ones: `id`, the 20 variables, `status`, `parse_status`, `parse_error`, `raw_text`, `input_tokens`, `output_tokens`, `model`, `effort`, `thinking`, `prompt_version` (`v3.0-all`), `prompt_sha256`, `data_kind`, `approval_note`, `run_at_utc`, `edsl_version`.
- `raw_text` holds only the model's JSON reply (about 510 characters at most). There is no transcript text in any file.
- Each file passes the rules in `code/explore_llm_questions.py` (`QUESTIONS`): every value is allowed, and nulls appear only where the rubric offers null. The rules were checked separately; your script was read, not run.
- The CSVs are force-added past `.gitignore` (`/outputs/llm_scores_real/`) at the instructor's direction, as with the v2.0 scores.
- The after-cutoff files hold the same 395 calls as the v2.0 after-cutoff file.

Example, not run here:

```
python code/explore_llm_questions.py \
    --scores gemma4=outputs/llm_scores_real/q2_2026_llm_scores_v3.0_gemma4_after_cutoff395.csv \
    --scores gptoss20b=outputs/llm_scores_real/q2_2026_llm_scores_v3.0_gptoss20b_after_cutoff395.csv \
    --scores qwen35_27b=outputs/llm_scores_real/q2_2026_llm_scores_v3.0_qwen35_27b_after_cutoff395.csv \
    --reference-llm outputs/llm_scores_real/q2_2026_llm_scores_v2.0_gemma4_after_cutoff395.csv
```

## The prompt

- **File:** `prompts/transcript_llm_scores_v3.0_all.txt`, SHA-256 `c92479102951cc43559428386e8fabb7f97ddcb955f63c861fc39ecca23d841f`, which matches `prompt_sha256` in every row.
- **Questions:** the 20 questions, scales and null options in `docs/LLM_QUESTIONS_V3_DRAFT.md` at `ce8355a`, word for word. The later edits to that file on `main` only change its "Open points" section.
- **Shared parts:** the preamble, the `status` / `incomplete_transcript` rule and the output instructions are copied from v2.0. Only two things change: "five variables" becomes "twenty variables", and the JSON template lists the 20 keys.
- **One addition:** Q20 also says "Judge this from the text of the call only, never from outside knowledge of the stock price." This is the draft's own note under Q20, put into the question.
- **Parsing:** the v2.0 rules apply (exact keys, allowed values, the `incomplete_transcript` rule, invalid replies stay missing), plus one more. **A null is valid only where the rubric offers null:** `margin_outlook`, `demand_trend`, `pricing_power`, `qa_vs_prepared` and `analyst_pushback`. Your loader enforces the same rule.

### One prompt, not four

The draft suggested four prompts of five questions each. Instead, all 20 went in one prompt per call. With these models, most of the run time goes into the reasoning they write before answering, not into reading the transcript. Four prompts would cost about four times as much.

On the 20 synthetic calls (`inputs/synthetic_v2_*`), Gemma's answers from one 20-question prompt and from two 10-question prompts agreed on 93% of the 400 answers. The differences were on judgment items, and they did not favor the split.

## Models and settings

| | Gemma 4 26B-A4B | gpt-oss-20b | Qwen3.5-27B |
|---|---|---|---|
| maker | Google | OpenAI | Alibaba (Qwen) |
| file | Unsloth `gemma-4-26B-A4B-it-UD-Q6_K_XL.gguf` | ggml-org `gpt-oss-20b-MXFP4.gguf` (native format) | Unsloth `Qwen3.5-27B-UD-Q5_K_XL.gguf` |
| training cutoff | January 2025 (Google's model card) | June 2024 (OpenAI's model card; check before citing) | not stated. The weights were published 2026-02-24 and haven't changed since, so they can't include the April–August 2026 calls. |
| median output tokens (incl. reasoning) | 6,371 | 1,503 | 7,169 |
| time for 474 calls | 3.0 h | 1.4 h | 7.8 h |

The three models come from three different makers, and all were trained before the first Q2 2026 call.

Settings for all three models:

- **Server:** llama.cpp `b12651` (CUDA) `llama-server` on one RTX 5090, with `-c 131072`, 4 parallel slots and `--jinja` (each model's own chat template, reasoning on).
- **EDSL:** 1.0.9 `QuestionFreeText`, local only: no remote inference, no remote cache, no proxy, in-memory cache.
- **Sampling:** temperature 0, `max_tokens` 16,384 (includes reasoning), one sample per call.
- **Reasoning cap:** `--reasoning-budget 12288`. When a model's reasoning reaches 12,288 tokens, the server ends it with the line "I have checked every variable. Final answer now." Then the model gives its answer.
- **Retries:** calls that did not parse were retried at most twice, one at a time, at temperature 0.7. At temperature 0, a retry tends to repeat the same failure.

### Why the reasoning cap, and how often it was reached

Without the cap, Gemma ran past 16,384 tokens on 6 of the first 16 real calls and returned nothing. Its reasoning settled all 20 answers, then kept re-checking the same five or six judgment items without changing them: `pricing_power`, `competitive_pressure`, `qa_vs_prepared`, `external_attribution`, `back_half_dependence` and `expected_investor_reaction`. At temperature 0 that cycle repeats until the token limit.

**The cap was reached often.** Gemma reached 12,288 or more output tokens on 206 of 474 calls, and Qwen on 182. On those calls, the cap cut the re-checking short and the model then answered. In the two looping calls whose reasoning was read before the cap was added (ABBV, ABT), every answer was already settled before the loop began. That is two calls, not a check of all of them, so keep it in mind for the judgment items.

gpt-oss produced 12,288 or more output tokens on 55 calls. The cap doesn't seem to work with gpt-oss's chat format, so its long calls relied on retries instead.

### Retries and missing calls

- **Gemma and Qwen:** every call parsed on the first try, and none of their replies broke the null rule.
- **gpt-oss:** 443 calls parsed on the first try, 29 on the second and 2 on the third.
- **gpt-oss null rule:** 28 gpt-oss replies first put `null` on variables with no null option, mostly `capex_change`. The null rule above was added after the main run, every saved reply was re-checked, and those 28 calls were scored again with the same settings. The replies that broke the rule are not used.
- **Missing:** one call, **SHW_2026-06-30**, still returned `null` for `capex_change` after two retries, so it is recorded as missing.

## Checks

- **Synthetic validation set (8 calls):** every model parsed all 8. There are no reference labels for the v3.0 questions, so this checks the format, not accuracy.
- **No repeat-sampling check:** each model scored each call once.

## Results at a glance (all 474 calls, usable rows)

#### Gemma 4 26B-A4B: 474/474 parsed

| variable | -1 | 0 | 1 | 2 | null |
|---|---|---|---|---|---|
| `outlook_vs_quarter` | 51 | 403 | 20 |  |  |
| `margin_outlook` | 30 | 162 | 253 |  | 29 |
| `demand_trend` | 16 | 54 | 404 |  |  |
| `back_half_dependence` |  | 276 | 198 |  |  |
| `guidance_framing` |  | 336 | 138 |  |  |
| `pricing_power` | 13 | 203 | 229 |  | 29 |
| `competitive_pressure` |  | 207 | 257 | 10 |  |
| `capex_change` | 11 | 405 | 58 |  |  |
| `capital_return_change` | 4 | 362 | 108 |  |  |
| `cost_program` |  | 264 | 160 | 50 |  |
| `qa_vs_prepared` | 23 | 449 | 2 |  |  |
| `analyst_pushback` |  | 392 | 53 | 29 |  |
| `new_adverse_disclosure` |  | 446 | 28 |  |  |
| `missed_own_target` |  | 414 | 60 |  |  |
| `external_attribution` |  | 27 | 421 | 26 |  |
| `balance_sheet_concern` |  | 461 | 13 |  |  |
| `leadership_change` |  | 394 | 80 |  |  |
| `corporate_action` |  | 286 | 188 |  |  |
| `ai_emphasis` |  | 135 | 122 | 217 |  |
| `expected_investor_reaction` | 28 | 41 | 405 |  |  |

#### gpt-oss-20b: 473/474 parsed

| variable | -1 | 0 | 1 | 2 | null |
|---|---|---|---|---|---|
| `outlook_vs_quarter` | 33 | 392 | 48 |  |  |
| `margin_outlook` | 28 | 84 | 217 |  | 144 |
| `demand_trend` | 19 | 46 | 406 |  | 2 |
| `back_half_dependence` |  | 338 | 135 |  |  |
| `guidance_framing` | 2 | 367 | 104 |  |  |
| `pricing_power` | 7 | 88 | 219 |  | 159 |
| `competitive_pressure` |  | 206 | 247 | 20 |  |
| `capex_change` | 13 | 410 | 50 |  |  |
| `capital_return_change` | 3 | 349 | 121 |  |  |
| `cost_program` |  | 383 | 61 | 29 |  |
| `qa_vs_prepared` | 9 | 427 | 37 |  |  |
| `analyst_pushback` |  | 446 |  | 27 |  |
| `new_adverse_disclosure` |  | 450 | 23 |  |  |
| `missed_own_target` |  | 468 | 5 |  |  |
| `external_attribution` |  | 131 | 331 | 11 |  |
| `balance_sheet_concern` |  | 464 | 9 |  |  |
| `leadership_change` |  | 411 | 62 |  |  |
| `corporate_action` |  | 317 | 156 |  |  |
| `ai_emphasis` |  | 160 | 144 | 169 |  |
| `expected_investor_reaction` | 5 | 92 | 376 |  |  |

#### Qwen3.5-27B: 474/474 parsed

| variable | -1 | 0 | 1 | 2 | null |
|---|---|---|---|---|---|
| `outlook_vs_quarter` | 45 | 406 | 23 |  |  |
| `margin_outlook` | 35 | 129 | 290 |  | 20 |
| `demand_trend` | 22 | 63 | 386 |  | 3 |
| `back_half_dependence` |  | 312 | 162 |  |  |
| `guidance_framing` |  | 358 | 116 |  |  |
| `pricing_power` | 26 | 124 | 273 |  | 51 |
| `competitive_pressure` |  | 142 | 320 | 12 |  |
| `capex_change` | 21 | 393 | 60 |  |  |
| `capital_return_change` | 4 | 358 | 112 |  |  |
| `cost_program` |  | 262 | 161 | 51 |  |
| `qa_vs_prepared` | 16 | 456 | 2 |  |  |
| `analyst_pushback` |  | 377 | 52 | 45 |  |
| `new_adverse_disclosure` |  | 418 | 56 |  |  |
| `missed_own_target` |  | 414 | 60 |  |  |
| `external_attribution` |  | 17 | 374 | 83 |  |
| `balance_sheet_concern` |  | 462 | 12 |  |  |
| `leadership_change` |  | 394 | 80 |  |  |
| `corporate_action` |  | 306 | 168 |  |  |
| `ai_emphasis` |  | 128 | 127 | 219 |  |
| `expected_investor_reaction` | 42 | 37 | 395 |  |  |

#### Agreement between models (share of the 474 calls with the same value)

| variable | Gemma vs gpt-oss | Gemma vs Qwen | gpt-oss vs Qwen |
|---|---|---|---|
| `outlook_vs_quarter` | 81% | 91% | 81% |
| `margin_outlook` | 58% | 78% | 59% |
| `demand_trend` | 87% | 89% | 82% |
| `back_half_dependence` | 72% | 81% | 68% |
| `guidance_framing` | 74% | 84% | 76% |
| `pricing_power` | 53% | 72% | 55% |
| `competitive_pressure` | 71% | 76% | 65% |
| `capex_change` | 93% | 95% | 91% |
| `capital_return_change` | 85% | 95% | 86% |
| `cost_program` | 69% | 85% | 68% |
| `qa_vs_prepared` | 86% | 94% | 87% |
| `analyst_pushback` | 80% | 81% | 76% |
| `new_adverse_disclosure` | 92% | 91% | 89% |
| `missed_own_target` | 88% | 94% | 88% |
| `external_attribution` | 68% | 80% | 59% |
| `balance_sheet_concern` | 96% | 98% | 96% |
| `leadership_change` | 94% | 93% | 90% |
| `corporate_action` | 80% | 86% | 83% |
| `ai_emphasis` | 82% | 91% | 80% |
| `expected_investor_reaction` | 77% | 88% | 73% |

This is exact agreement; a null on both sides counts as agreeing. Your script also reports kappa and Spearman.

Things to think about before the analysis:

- **Rare in every model:** `qa_vs_prepared` is about 95% zero and `balance_sheet_concern` about 97% zero. `new_adverse_disclosure` is also rare, and gpt-oss almost never gives `missed_own_target` (5 of 473).
- **Leaning one way:** `expected_investor_reaction` is +1 on about 80–85% of calls, and `demand_trend` on about 85%.
- **Spread out:** `ai_emphasis`, `corporate_action`, `cost_program`, `back_half_dependence`, `guidance_framing`, `competitive_pressure` and `margin_outlook`.
- **Lowest agreement:** `pricing_power`, `margin_outlook` and `external_attribution`. gpt-oss is the odd one out on these, and it uses null far more often on `margin_outlook` and `pricing_power`.
- **Closest pair:** Gemma and Qwen agree most often. That doesn't show either one is right.
