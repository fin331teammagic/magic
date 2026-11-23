# Run 3 LLM scores on the Q2 2026 cohort: instructor's local run (2026-11-23)

Professor Bowen scored the cohort's real transcripts with an open-weight model on his own computer. The transcript text never left that machine. This file records how the run was done. The scores are in `outputs/llm_scores_real/`.

## Files

| file | rows | parsed |
|---|---|---|
| `outputs/llm_scores_real/q2_2026_llm_scores_v2.0_gemma4_after_cutoff395.csv` | 395, the `--after-cutoff-only` sample in `specs_tried.md` amendment 2 | 394 (CFG missing) |
| `outputs/llm_scores_real/q2_2026_llm_scores_v2.0_gemma4_all474.csv` | all 474 matched calls | 472 (CFG and PAYX missing) |

- The columns are the same 21 that `code/score_transcripts_edsl.py` writes.
- `raw_text` holds only the model's JSON reply (150 characters at most). There is no transcript text in either file.
- These files are force-added past `.gitignore` (`/outputs/llm_scores_real/`) at the instructor's direction.

## What was asked

- **Prompt:** your frozen `prompts/transcript_llm_scores_v2.0.txt`, byte for byte. SHA-256 `9a9bc0cb018ccf5a8154cde1725cf4c2ee7ee05e3a4cfad705f297449e6d8f6e`, which matches `prompt_sha256` in every row.
- **Question:** one EDSL `QuestionFreeText` per call.
- **Parsing:** your `parse_response` rules (exact keys, allowed values, the `incomplete_transcript` rule). Invalid replies stay missing.
- **Retries:** calls that didn't parse were retried at most twice, as `specs_tried.md` §4 says.

## Sample

- `restricted_data/` held the course's Capital IQ files (`calls_sp500_2024_2026.csv`, `call_fulltext_2024_2026.parquet`).
- `code/build_transcript_inputs.py` ran at `76e4464`. The only change was its default paths.
- It reproduced your coverage numbers:
  - 474 of 499 events matched: 452 `matched`, 21 `matched_by_period_end`, 1 `matched_multiple`.
  - 395 of the 474 are after the 2026-06-30 cutoff.
  - The transcript data ends 2026-08-07.
- The 21 `matched_by_period_end` events are scored too. Amendment 3's day-0 exclusion is still yours to apply.

## Model and settings

| | |
|---|---|
| model | Google Gemma 4 26B-A4B-it, Unsloth GGUF `gemma-4-26B-A4B-it-UD-Q6_K_XL.gguf` |
| knowledge cutoff | pre-training data through January 2025, as recorded in the instructor's setup notes. Check Google's model card before you cite it. Every cohort call (Apr–Aug 2026) is after it, so the 79 calls before Claude's June 2026 cutoff are also usable with this model, if you amend the spec |
| server | llama.cpp `b12651` (CUDA) `llama-server` on an RTX 5090: `-c 131072`, 4 parallel slots, `--jinja` chat template |
| EDSL | 1.0.9, `service_name="openai_compatible"`, with `disable_remote_inference`, `disable_remote_cache`, `offload_execution=False`, `use_api_proxy=False`, and an in-memory `Cache` |
| sampling | temperature 0; `max_tokens` 16,384 (includes reasoning); one sample per call |
| run | 2026-11-23, 11:08–13:30 ET; about 17 s per call |

The `model` column says `local/gemma-4-26B-A4B-it-UD-Q6_K_XL (llama.cpp b12651, temperature 0, max_tokens 16384)`. `effort` is `n/a`, and `thinking` is `model default (reasoning on)`.

## Results at a glance (474 calls)

| variable | −1 | 0 | 1 | 2 | null |
|---|---|---|---|---|---|
| `guidance_specificity` | | 3 | 14 | 455 | 2 |
| `guidance_revision` | 38 | 145 | 236 | | 55 |
| `qa_evasiveness` | | 313 | 158 | 1 | 2 |
| `one_off_attribution` | 93 | 241 | 138 | | 2 |
| `analyst_concern_focus` | | 67 | 354 | 51 | 2 |

Things to think about before Run 3:
- `guidance_specificity` is 2 for 96% of calls, and `qa_evasiveness` is almost never 2. Variables that barely vary can't explain much.
- `guidance_revision` is null for 55 calls, which shrinks the complete-case sample.

## Checks

- **Synthetic validation set** (8 calls, `inputs/synthetic_v2_validation*`): 8 of 8 agree with the reference labels on every field.
- **Synthetic development set** (12 calls): 12 of 12 parsed, with one disagreement: SYN2-D03 `guidance_specificity` is 2, and the reference is 1.
- **One run only.** These are single temperature-0 runs. No repeated-sampling or second-model reliability check has been done on real calls.

## Notes on `abby/local-llm`

The scorer on that branch would mostly produce empty or failed rows with a reasoning model like this one, for three reasons:

1. **`--max-tokens` is too low.** Gemma 4 reasons before it answers. Its output averaged about 4.5K tokens per real call (median 4,544), and 2 calls ran past 16,384 on all 3 tries. With the default 1024, or the suggested 4096, the reply is cut off before the JSON and comes back empty. Use at least 16384.
2. **EDSL's request timeout is 60 s by default** (`EDSL_API_TIMEOUT`). Requests that queue behind the server's parallel slots time out with no reply. Set `EDSL_API_TIMEOUT=3600` before you import EDSL.
3. **Context.** The longest matched call is about 28K tokens before reasoning (99K characters, at 3.5 characters per token), and the parallel slots share one KV pool. A 32K window per request is tight once reasoning is added. This run used 128K shared across 4 slots.
