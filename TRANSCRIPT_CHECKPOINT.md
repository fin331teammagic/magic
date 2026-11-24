# Transcript-feature checkpoint

> **Status, 2026-11-23: scoring is done.** The course lead scored all 474
> matched calls on his own computer with Gemma 4 (`docs/LOCAL_LLM_INSTRUCTOR_RUN.md`,
> PR #22), and the team adopted those scores in `specs_tried.md` Amendment 5.
> Results are in §8 (runs 12–19). The enterprise-key route, the Sonnet
> sign-off and the guidance-null decision below are therefore **superseded**:
> no key was used, Sonnet did not score real calls, and nulls are dropped in
> the primary run and kept as their own category in a robustness run. The
> rest of this file is kept as the record of how the inputs and prompt were
> built.

## Scope and safeguards

This is a low-cost workflow check, not the final research scoring protocol or
evidence about the S&P 500 cohort. Use synthetic transcripts only with
external AI.

Licensed transcript text must never be uploaded to GitHub, pasted into a web
chat, or sent to Expected Parrot's servers.

Update, 2026-11-19. Professor Bowen's latest message describes the intended
route: run EDSL on our own computer, with Expected Parrot's remote
inference and cache turned off, and send transcripts straight to Anthropic's
API under the course's enterprise account, which he understands has a
no-training provision. His message conditions this on that access being in
place ("assuming that I have access to it"), and his earlier data memo says
cloud models stay off limits until he confirms the enterprise setup. So
before any real-transcript run:

1. get his written confirmation that the enterprise account is set up and
   that we may send the course transcripts through it, and record it in
   `--approval-note`;
2. use an `ANTHROPIC_API_KEY` issued by that enterprise workspace, not a
   personal key (the scorer checks only that a key is set, not which account
   it belongs to).

Until both are done, use synthetic transcripts only.

The final study's proposed model remains the pinned checkpoint documented in
`PROPOSAL.md`; this exploratory Claude checkpoint does not replace it.

## Features for this checkpoint

Score only management's forward-looking statements, not analysts' questions,
historical results, external facts, or market reaction.

- `outlook_tone`: integer from -2 to +2. Use -2 for materially worsening,
  -1 for somewhat worsening, 0 for stable or mixed, +1 for somewhat improving,
  and +2 for materially improving expectations. Use `null` when the transcript
  has no usable management outlook.
- `guidance_specificity`: integer from 0 to 2. Use 0 when management gives no
  forward guidance, 1 for qualitative or directional guidance (even if a
  future period is named), and 2 for numerical guidance such as a target or
  range tied to a period.

`status` is `scored`, `insufficient_outlook`, or `incomplete_transcript`.
For a complete transcript with no usable outlook, return a null tone, zero
guidance specificity, and `insufficient_outlook`. If the transcript is
incomplete or unreadable, return null for both scores and
`incomplete_transcript`. Missing information must not be converted to a
neutral score.

## Prompt (version 1.2)

Use one transcript per request and ask for both scores in that single request.
For a real-data checkpoint, use Claude Haiku directly, not Expected Parrot.
Turn off reasoning or use the lowest setting; if the interface exposes an
output-token limit, start at 128 and increase only if valid JSON is truncated.

```text
Score the management outlook in the single earnings-call transcript below.
Use only this transcript. Do not use outside knowledge, browse, infer stock
returns, or use information learned after the call. Score management
statements, not analysts' views. Do not quote the transcript or include
explanations.

outlook_tone: -2 materially worsening, -1 somewhat worsening, 0 stable or
mixed, +1 somewhat improving, +2 materially improving. Use null if there is
no usable management outlook.

guidance_specificity: 0 no forward guidance, 1 qualitative or directional
guidance even if a future period is named, 2 numerical guidance such as a
target or range tied to a period.

status: scored if outlook can be assessed; insufficient_outlook if there is
no usable management outlook; incomplete_transcript if the transcript is
incomplete or unreadable. For insufficient_outlook, use null for
outlook_tone and 0 for guidance_specificity. For incomplete_transcript, use
null for both scores.

Return exactly one JSON object with these keys and no other text:
{"outlook_tone": <integer or null>,
 "guidance_specificity": <integer or null>,
 "status": "<scored|insufficient_outlook|incomplete_transcript>"}
Use standard ASCII double quotes, not typographic quotes, so the response is
valid JSON. Do not wrap it in a Markdown code fence.

Transcript:
<PASTE ONE SYNTHETIC TRANSCRIPT HERE>
```

## Single-excerpt dry run

The following invented example is SYN-001 in the 20-excerpt fixture. It is
synthetic and not based on an issuer transcript.

> Management: Customer demand has strengthened for three consecutive months.
> We now expect full-year revenue growth of 6% to 8%, up from our prior
> expectation of 3% to 5%. We are confident in that range, although currency
> movements may create some volatility.

Claude Haiku 5.5 (Low effort) was run twice on November 13, 2026 with the
synthetic example above, first with prompt version 1.0 and then 1.1. Both
runs returned `outlook_tone=2`, `guidance_specificity=2`, and `status=scored`.
The Claude web interface did not expose a maximum-output-token setting. Its
displayed response used typographic quotes even with version 1.1's ASCII-only
instruction, so strict JSON parseability remains unverified. Before a larger
run, manually verify copied output or record the three values directly in the
run log.

Expected scores and status:

```json
{
  "outlook_tone": 2,
  "guidance_specificity": 2,
  "status": "scored"
}
```

Claude Haiku 5.5 (Low effort) was run twice on November 13, 2026 with this
synthetic example, first using prompt version 1.0 and then 1.1. Both runs
returned the expected scores and status. The Claude web interface did not
expose a maximum-output-token setting. Its displayed response used
typographic quotes even with version 1.1's ASCII-only instruction, so strict
JSON parseability remains unverified.

## Twenty-mini-call batch check

The JSONL file contains 20 fictional mini-calls, including improving, stable,
worsening, no-outlook, and explicitly incomplete cases. They can be scored
together in one request as a low-cost format experiment. This batch approach
applies only to these synthetic mini-calls. No real transcript text is
authorized for external model requests. The mock calls are much shorter than
real full-length calls, so this tests scoring and output format but not
real-call token cost.

The first batch exposed ambiguity between qualitative outlooks that name a
future period and numerical guidance. Prompt version 1.2 clarifies that a
period alone does not make qualitative guidance specific. Paste the JSONL
records after this prompt. Do not include
`inputs/synthetic_transcript_expected_scores.csv`.

```text
Score each synthetic call excerpt independently using only its own text.
Apply these definitions: outlook_tone is -2 to +2 or null;
guidance_specificity is 0 for no forward guidance, 1 for qualitative or
directional guidance even if a future period is named, and 2 for numerical
guidance such as a target or range tied to a period; status is scored,
insufficient_outlook, or incomplete_transcript. For a complete excerpt with
no usable outlook, return null, 0, insufficient_outlook. For an explicitly
incomplete excerpt, return null, null, incomplete_transcript.

Return exactly one TSV header and one row per ID, with these columns:
id<TAB>outlook_tone<TAB>guidance_specificity<TAB>status
Use null for null values. Do not use quotes, code fences, explanations, or
extra rows.

Synthetic excerpts:
<PASTE THE CONTENTS OF inputs/synthetic_transcript_checkpoint.jsonl HERE>
```

Compare Claude's rows with the separate expected-score CSV. Record
disagreements, incorrect IDs, missing rows, and output-format errors. Agreement
on invented excerpts is not evidence of predictive validity.

On November 13, 2026, Claude Haiku 5.5 at Low effort scored all 20 expanded
mock calls using prompt version 1.2. The output is saved in
`inputs/synthetic_transcript_checkpoint_claude_scores.csv` and matches all 20
reference rows. The rubric and two reference labels were clarified after the
earlier short-excerpt batch, then the same examples were expanded and run
again; this 20/20 agreement is a prompt-debugging result, not an independent
accuracy estimate. The web interface did not expose a maximum-output-token
setting.

## Blind synthetic validation

The separate 10-call validation set is in
`inputs/synthetic_transcript_validation.jsonl`. Its reference labels are in
`inputs/synthetic_transcript_validation_expected.csv`; keep that file out of
the model prompt. Those labels were set before the validation run. Prompt
version 1.2 was frozen before scoring, and neither the prompt nor the labels
were changed afterward.

Claude Haiku 5.5 at Low effort returned 10 rows, all matching the reference
labels. The results are in
`inputs/synthetic_transcript_validation_claude_scores.csv`. This checks
consistency on invented examples only; it is not evidence that the scores are
accurate for real calls or useful for return prediction.

## Minimal run log

Keep the run log separate from transcript text. For synthetic runs, record the
event identifier, model/version shown by the client (and exact API model
identifier if available), prompt version, run date, status, scores, and any
error. Do not save transcript text, quotations, or model explanations in the
log. Preserve incomplete and failed records as such. Under the current
instruction, do not send real transcript text to an external model.

Do not interpret this checkpoint as a predictive test. A 20-call exercise is
only a workflow and coverage feasibility check; the final study requires
authorized coverage, a pinned model and rubric, and the planned chronological
comparison on a shared sample.

## Version 2.0: the five Run 3 LLM variables

Version 2.0 replaces the v1.2 rubric for the main study design in
`specs_tried.md` (three nested regressions, following the course lead's
guidance). It drops `outlook_tone`, which largely re-measures dictionary
sentiment, and scores five variables that need context to measure:
`guidance_specificity`, `guidance_revision`, `qa_evasiveness`,
`one_off_attribution` and `analyst_concern_focus`.

- **Prompt (frozen):** `prompts/transcript_llm_scores_v2.0.txt`. The script
  records its SHA-256 with every score. The prompt tells the model that the
  transcript is data and that instructions inside it must be ignored.
- **Scorer:** `code/score_transcripts_edsl.py`. It uses Expected Parrot's EDSL
  library with local execution only: every run passes
  `disable_remote_inference=True`, `disable_remote_cache=True`,
  `offload_execution=False` and `use_api_proxy=False`, and keeps EDSL's cache in
  memory. (EDSL 1.0.9 defaults `offload_execution` to True, so the flags are
  required.) The default is a dry run that prints the request count and an
  estimated cost. `--run` calls the API. The script refuses to run if a `.env`
  file is visible to EDSL. With `--data-kind real`, it requires git-ignored
  input and output files and an approval note.
- **Synthetic sets:**
  - development: 12 calls, `inputs/synthetic_v2_development.jsonl`;
  - validation: 8 calls, `inputs/synthetic_v2_validation.jsonl`.

  Each has a reference-label CSV, which is never sent to the model. Both sets
  cover every level of every variable, an explicitly incomplete transcript,
  calls with no Q&A, and an embedded instruction that the model must ignore.
  The same person wrote the calls and the labels before any model run, so
  agreement checks consistency with the rubric, not independent accuracy.
- **Order of runs:** the development set first (any prompt change creates a
  new version), then the validation set once with the prompt frozen. Record
  both in the `specs_tried.md` run log. Real transcripts only after written
  approval (see Scope above).

Example dry run, then a real synthetic run:

```bash
python code/score_transcripts_edsl.py \
  --input-jsonl inputs/synthetic_v2_development.jsonl \
  --prompt prompts/transcript_llm_scores_v2.0.txt --prompt-version 2.0 \
  --model claude-sonnet-5-5 --effort low \
  --output-csv outputs/llm_scores/synthetic_v2_development_sonnet_low.csv \
  --expected-csv inputs/synthetic_v2_development_expected.csv
# add --run to send the 12 synthetic calls
```

## Real transcripts for the Q2 2026 cohort (built 2026-11-19; not yet scored)

- **Data:** the course's S&P Capital IQ transcripts (via WRDS), 2024-01-05 to
  2026-08-07, 5,374 calls, in `restricted_data/` (git-ignored) as
  `*_2024_2026.*`. The earlier `*_2024_2025.*` download, which stopped at
  2025-12-19, is archived in `restricted_data/archive_2024_2025/`.
- **Matching:** `code/build_transcript_inputs.py` matches each event in
  `inputs/q2_2026_events.csv` to a live earnings call (pre-recorded calls
  excluded) by CIK, then ticker, with a call date 1 day before to 3 days after
  the earnings date. It writes, inside `restricted_data/llm_inputs/`, a
  match file with no transcript text and `q2_2026_calls.jsonl`, the scorer's
  input. `--after-cutoff-only` writes only calls after the training cutoff.
- **Coverage (499 cohort events):**

  | Status | Events |
  |---|---|
  | matched within the earnings-date window | 452 |
  | matched within the window, two candidate calls (Micron held two sessions; the closer one is used) | 1 |
  | matched by fiscal period end (see below) | 21 |
  | not matched: call after the data end (2026-08-07) | 9 |
  | not matched: firm not in the transcript data | 14 |
  | not matched: no call for that quarter (AES, SMCI) | 2 |
  | **matched, total** | **474** |

  Unmatched events stay in the match file with a reason. The 25 unmatched
  events must be reported as missing transcript coverage, not dropped.
- **Earnings-date mismatch, 21 events:** for ABBV, APA, APO, ARES, BIIB, EOG,
  EQT, ES, FANG, GEHC, HCA, HONA, IBM, NKE, OXY, PGR, PNR, PRU, REGN, RMD and
  TSLA, no call falls near the cohort's `earnings_timestamp` (an SEC 8-K
  Item 2.02 acceptance time). The earnings call is 6 to 37 days later; for
  example, Tesla's 8-K is dated July 2 and its call July 22. These events are
  matched to the first call after the fiscal period end and flagged
  `matched_by_period_end`. **Their `day0_session`, and therefore the event
  window and CARs, may be dated on an earlier 8-K rather than the results
  release; check them before the return analysis.**
- **Training cutoff:** Claude Haiku 5.5, Sonnet 5.5 and Opus 5.5 all list a
  June 2026 reliable-knowledge and training-data cutoff (Anthropic models
  overview, retrieved 2026-11-19). 395 of the 474 matched calls are after
  2026-06-30. The other 79 (calls from 2026-04-23 to 2026-06-30, mostly
  fiscal quarters ending in April or May) fall within the training window
  and are flagged `after_training_cutoff = False`. Decide before scoring
  whether to score only the 395 or to score all and test the 79 separately.
  A cutoff before a call does not prove the call is absent from training.
- **Estimated cost** (from word counts, about 1.4 tokens per word, at low
  effort): 474 calls are about 6.0M input tokens, about $0.62 with
  Haiku 5.5 and $12.40 with Sonnet 5.5; the 395 post-cutoff calls about
  $0.52 and $10.34. The longest call is about 16,800 words, well under
  Haiku 5.5's 100K-token price tier and every model's 1M context window. Run
  the scorer's dry run (no `--run`) for its own estimate.

Real-transcript run, once the two approval steps in Scope are done.

**Updated 2026-11-22.** The sample decision is made: only the 395
post-cutoff calls (`specs_tried.md` Amendment 2). Sonnet 5.5 is the proposed
model; it agreed with 47 of 48 synthetic validation labels (§8, runs 6–8).
The [TEAM] sign-off on the model is still pending.

The input file is already built:
`restricted_data/llm_inputs/q2_2026_calls_after_cutoff.jsonl`. EDSL needs
Python 3.12. The `edsl312` conda environment has it, and `magic312` has the
pinned project environment.

1. Score the calls.

   ```bash
   export ANTHROPIC_API_KEY=...   # enterprise-workspace key; never commit or paste it
   S="conda run -n edsl312 python code/score_transcripts_edsl.py \
     --input-jsonl restricted_data/llm_inputs/q2_2026_calls_after_cutoff.jsonl \
     --prompt prompts/transcript_llm_scores_v2.0.txt --prompt-version 2.0 \
     --model claude-sonnet-5-5 --effort low --data-kind real \
     --approval-note '<who approved, date, enterprise workspace>' \
     --output-csv restricted_data/llm_outputs/q2_2026_sonnet_scores.csv"
   eval "$S"                       # dry run: plan and cost, nothing sent
   eval "$S --limit 3 --run"       # three calls first; check the output
   eval "$S --run --overwrite"     # all 395 (about $10 with Sonnet)
   ```

   To confirm the route during the real run, start the scorer through
   `code/trace_network_hosts.py`. It prints every host contacted:

   ```bash
   conda run -n edsl312 python code/trace_network_hosts.py code/score_transcripts_edsl.py <same args>
   ```

   **Check, 2026-11-23:** one invented validation call (SYN2-V01) was scored
   with Haiku 5.5 through this wrapper. The only host contacted was
   `api.anthropic.com`; there was no `expectedparrot.com` or other host.
   The check logs lookups made through Python's socket module, which is how
   EDSL and the Anthropic SDK connect.

2. Run the pre-specified nested comparison. It evaluates the holdout once,
   so log it in `specs_tried.md` §8.

   ```bash
   conda run -n magic312 python code/run_nested_models.py \
     --llm-scores restricted_data/llm_outputs/q2_2026_sonnet_scores.csv
   ```

   It writes `outputs/model_runs.csv`, `model_coefficients.csv`,
   `run_predictions.csv` and `nested_sample_flow.csv`. To show them on the
   dashboard, point the `model_runs`, `model_coefficients` and
   `run_predictions` entries in `dashboard/data_registry.py` at these files.

**Before scoring: open [TEAM] decision.** The prompt returns
`guidance_revision = null` when the call gives no way to compare with prior
guidance. Under §2's complete-case rule, every such call drops out of all
three runs. Decide, and record as an amendment before scoring, whether to:
- keep complete case, as now; or
- code null as its own category, for example 0 plus a `no_prior_guidance`
  indicator. That is not a zero-fill of missing data, because null is a
  defined answer.
