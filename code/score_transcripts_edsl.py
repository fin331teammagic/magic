"""Score earnings-call transcripts with Claude through EDSL, locally only.

Implements the Run 3 LLM variables in ``specs_tried.md`` with the frozen
prompt in ``prompts/``. Every run is local: EDSL calls Anthropic directly with
the ANTHROPIC_API_KEY environment variable, and nothing is sent to Expected
Parrot's servers or remote cache.

Safety rules built into this script:

- The default is a dry run, which prints the number of requests and an
  estimated cost and sends nothing. Pass ``--run`` to call the API.
- It refuses to run if a ``.env`` file exists in the working directory, the
  EDSL install directory, or any parent of either (EDSL auto-loads them).
  File names are checked, never contents.
- The API key's value is never read, printed or logged; only its presence is
  checked.
- ``--data-kind synthetic`` accepts only IDs that start with ``SYN``.
  ``--data-kind real`` requires the input and output files to be git-ignored
  and an ``--approval-note`` recording who approved sending the text.
- The EDSL response cache is kept in memory, so transcript text is not
  written to EDSL's cache on disk.

Run from the repository root, for example:

    python code/score_transcripts_edsl.py \
        --input-jsonl inputs/synthetic_v2_development.jsonl \
        --prompt prompts/transcript_llm_scores_v2.0.txt --prompt-version 2.0 \
        --model claude-sonnet-5-5 --effort low \
        --output-csv outputs/llm_scores/synthetic_v2_development_scores.csv \
        --expected-csv inputs/synthetic_v2_development_expected.csv
"""

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

ALLOWED_VALUES = {
    "guidance_specificity": {0, 1, 2},
    "guidance_revision": {-1, 0, 1},
    "qa_evasiveness": {0, 1, 2},
    "one_off_attribution": {-1, 0, 1},
    "analyst_concern_focus": {0, 1, 2},
}
VARIABLES = tuple(ALLOWED_VALUES)
STATUSES = {"scored", "incomplete_transcript"}
TEMPLATE_VARIABLE = "{{ scenario.transcript }}"

# Anthropic first-party list prices, USD per million tokens (input, output),
# from the Claude API reference cached 2026-11-03. Haiku 5.5's price applies
# to prompts up to 100K tokens. Check current prices before a large run.
PRICES_PER_MILLION = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}
# Turn extended thinking off where the model allows it. Opus 5.5 cannot
# disable thinking, so it runs with adaptive thinking at the chosen effort.
THINKING_OFF = {
    "claude-sonnet-5-5": {"type": "between_tools"},
    "claude-haiku-5-5": {"type": "disabled"},
}
LOCAL_ONLY_RUN_FLAGS = {
    "disable_remote_inference": True,
    "disable_remote_cache": True,
    "offload_execution": False,
    "use_api_proxy": False,
}
CHARS_PER_TOKEN_ESTIMATE = 3.5  # conservative for English text
ESTIMATED_OUTPUT_TOKENS = 80
OUTPUT_COLUMNS = (
    ["id", *VARIABLES, "status", "parse_status", "parse_error", "raw_text"]
    + ["input_tokens", "output_tokens", "model", "effort", "thinking"]
    + ["prompt_version", "prompt_sha256", "data_kind", "approval_note"]
    + ["run_at_utc", "edsl_version"]
)


def find_dotenv_files(start_dirs):
    """Return paths of .env* files in each start directory and its parents."""
    found = set()
    for start in start_dirs:
        directory = Path(start).resolve()
        for folder in [directory, *directory.parents]:
            try:
                names = os.listdir(folder)
            except OSError:
                continue
            for name in names:
                if name == ".env" or name.startswith(".env."):
                    found.add(str(folder / name))
    return sorted(found)


def is_git_ignored(path):
    """Return True if git would ignore ``path`` in the current repository."""
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(path)],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def load_calls(jsonl_path):
    """Load ``{"id", "transcript"}`` records and check IDs are unique."""
    calls = []
    seen = set()
    with open(jsonl_path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            call_id = record.get("id")
            transcript = record.get("transcript")
            if not isinstance(call_id, str) or not call_id.strip():
                raise ValueError(f"Line {line_number}: missing or empty id.")
            if not isinstance(transcript, str) or not transcript.strip():
                raise ValueError(f"Line {line_number}: missing or empty transcript.")
            if call_id in seen:
                raise ValueError(f"Duplicate id: {call_id}")
            seen.add(call_id)
            calls.append({"id": call_id, "transcript": transcript})
    if not calls:
        raise ValueError("No transcripts found in the input file.")
    return calls


def load_prompt(prompt_path):
    """Load the prompt template and check it contains the transcript variable."""
    template = Path(prompt_path).read_text(encoding="utf-8")
    if template.count(TEMPLATE_VARIABLE) != 1:
        raise ValueError(
            f"Prompt must contain {TEMPLATE_VARIABLE} exactly once."
        )
    return template


def empty_scores():
    return {name: None for name in VARIABLES} | {"status": None}


def parse_response(text):
    """Parse one model reply into validated scores.

    Returns a dict with the five variables, ``status``, ``parse_status``
    (``ok`` or ``error``) and ``parse_error``. Invalid replies keep every
    score missing; they are never converted to a default value.
    """
    result = empty_scores() | {"parse_status": "error", "parse_error": ""}
    if text is None or not str(text).strip():
        result["parse_error"] = "empty response"
        return result
    cleaned = str(text).strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as error:
        result["parse_error"] = f"invalid JSON: {error.msg}"
        return result
    if not isinstance(payload, dict):
        result["parse_error"] = "response is not a JSON object"
        return result
    expected_keys = set(VARIABLES) | {"status"}
    if set(payload) != expected_keys:
        missing = sorted(expected_keys - set(payload))
        extra = sorted(set(payload) - expected_keys)
        result["parse_error"] = f"keys mismatch; missing={missing} extra={extra}"
        return result
    status = payload["status"]
    if status not in STATUSES:
        result["parse_error"] = f"invalid status: {status!r}"
        return result
    values = {}
    for name in VARIABLES:
        value = payload[name]
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value not in ALLOWED_VALUES[name]
        ):
            result["parse_error"] = f"invalid value for {name}: {value!r}"
            return result
        values[name] = value
    if status == "incomplete_transcript" and any(
        value is not None for value in values.values()
    ):
        result["parse_error"] = "incomplete_transcript must have all scores null"
        return result
    return values | {"status": status, "parse_status": "ok", "parse_error": ""}


def extract_text(raw_response, fallback=None):
    """Join the text blocks of an Anthropic Messages response.

    Thinking blocks are skipped. Falls back to EDSL's parsed answer when the
    raw response has no Anthropic ``content`` list.
    """
    if isinstance(raw_response, dict) and isinstance(raw_response.get("content"), list):
        texts = [
            block.get("text", "")
            for block in raw_response["content"]
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "".join(texts)
    return fallback


def estimate_cost(calls, template, model):
    """Estimate request count, tokens and USD cost without calling the API."""
    if model not in PRICES_PER_MILLION:
        raise ValueError(f"No price recorded for {model}; add it before running.")
    input_price, output_price = PRICES_PER_MILLION[model]
    prompt_chars = len(template) - len(TEMPLATE_VARIABLE)
    input_tokens = sum(
        math.ceil((prompt_chars + len(call["transcript"])) / CHARS_PER_TOKEN_ESTIMATE)
        for call in calls
    )
    output_tokens = ESTIMATED_OUTPUT_TOKENS * len(calls)
    cost = input_tokens / 1e6 * input_price + output_tokens / 1e6 * output_price
    return {
        "requests": len(calls),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
        "largest_call_chars": max(len(call["transcript"]) for call in calls),
    }


def read_expected(expected_csv):
    expected = {}
    with open(expected_csv, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            expected[row["id"]] = {
                name: (None if row[name] in ("", "null") else int(row[name]))
                for name in VARIABLES
            } | {"status": row["status"]}
    return expected


def compare_to_expected(rows, expected):
    """Count agreement per variable and list every disagreement."""
    fields = [*VARIABLES, "status"]
    agreement = {field: 0 for field in fields}
    disagreements = []
    compared = 0
    for row in rows:
        reference = expected.get(row["id"])
        if reference is None:
            continue
        compared += 1
        for field in fields:
            if row[field] == reference[field]:
                agreement[field] += 1
            else:
                disagreements.append((row["id"], field, row[field], reference[field]))
    missing = sorted(set(expected) - {row["id"] for row in rows})
    return {
        "compared": compared,
        "agreement": agreement,
        "disagreements": disagreements,
        "missing_ids": missing,
    }


def check_safety(args, calls):
    """Stop before any API call if a safety rule is not met."""
    import edsl  # noqa: F401  (import only to locate the install directory)

    edsl_dir = Path(edsl.__file__).resolve().parent
    dotenv = find_dotenv_files([Path.cwd(), edsl_dir])
    if dotenv:
        raise SystemExit(
            "Refusing to run: EDSL would auto-load these .env files: "
            + ", ".join(dotenv)
        )
    if args.data_kind == "synthetic":
        bad = [call["id"] for call in calls if not call["id"].startswith("SYN")]
        if bad:
            raise SystemExit(
                "Refusing to run: --data-kind synthetic but these IDs do not "
                f"start with SYN: {bad[:5]}"
            )
    else:
        if not args.approval_note:
            raise SystemExit("Refusing to run: real data needs --approval-note.")
        for label, path in (("input", args.input_jsonl), ("output", args.output_csv)):
            if not is_git_ignored(path):
                raise SystemExit(
                    f"Refusing to run: the {label} file {path} is not git-ignored."
                )
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Refusing to run: ANTHROPIC_API_KEY is not set.")


def summarize_exceptions(results):
    """Return short, de-duplicated messages for exceptions EDSL recorded."""
    messages = []
    history = getattr(results, "task_history", None)
    for interview in getattr(history, "total_interviews", []) or []:
        for exceptions in getattr(interview, "exceptions", {}).values():
            for entry in exceptions:
                error = getattr(entry, "exception", entry)
                text = f"{type(error).__name__}: {str(error)[:400]}"
                if text not in messages:
                    messages.append(text)
    return messages


def run_scoring(args, calls, template):
    """Score every call with EDSL, locally, and return output rows."""
    import edsl
    from edsl import Cache, Model, QuestionFreeText, Scenario, ScenarioList

    thinking = THINKING_OFF.get(args.model)
    model = Model(
        args.model,
        service_name="anthropic",
        max_tokens=args.max_tokens,
        thinking=thinking,
        output_config={"effort": args.effort},
    )
    question = QuestionFreeText(question_name="scores", question_text=template)
    scenarios = ScenarioList(
        [Scenario({"id": call["id"], "transcript": call["transcript"]}) for call in calls]
    )
    results = question.by(scenarios).by(model).run(
        **LOCAL_ONLY_RUN_FLAGS,
        cache=Cache(data={}),
        progress_bar=False,
        print_exceptions=True,
    )
    for message in summarize_exceptions(results):
        print(f"EDSL exception: {message}")
    columns = [
        "scenario.id",
        "answer.scores",
        "raw_model_response.scores_raw_model_response",
        "raw_model_response.scores_input_tokens",
        "raw_model_response.scores_output_tokens",
    ]
    available = set(results.columns)
    present = [column for column in columns if column in available]
    by_id = {}
    for values in results.select(*present).to_list():
        if len(present) == 1:
            values = (values,)
        record = dict(zip(present, values))
        by_id[record["scenario.id"]] = tuple(record.get(column) for column in columns[1:])

    run_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    prompt_sha = hashlib.sha256(template.encode("utf-8")).hexdigest()
    rows = []
    for call in calls:
        answer, raw, input_tokens, output_tokens = by_id.get(
            call["id"], (None, None, None, None)
        )
        text = extract_text(raw, fallback=answer)
        parsed = parse_response(text)
        rows.append(
            {"id": call["id"]}
            | parsed
            | {
                "raw_text": text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "model": args.model,
                "effort": args.effort,
                "thinking": json.dumps(thinking) if thinking else "adaptive",
                "prompt_version": args.prompt_version,
                "prompt_sha256": prompt_sha,
                "data_kind": args.data_kind,
                "approval_note": args.approval_note or "",
                "run_at_utc": run_at,
                "edsl_version": getattr(edsl, "__version__", ""),
            }
        )
    return rows


def write_rows(rows, output_csv):
    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {key: ("null" if row.get(key) is None and key in (*VARIABLES, "status") else row.get(key)) for key in OUTPUT_COLUMNS}
            )


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--input-jsonl", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--prompt-version", required=True)
    parser.add_argument("--model", required=True, choices=sorted(PRICES_PER_MILLION))
    parser.add_argument(
        "--effort", default="low", choices=["low", "medium", "high", "xhigh", "max"]
    )
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--data-kind", choices=["synthetic", "real"], default="synthetic")
    parser.add_argument("--approval-note", default="")
    parser.add_argument("--expected-csv", help="Reference labels (synthetic only).")
    parser.add_argument("--limit", type=int, help="Score only the first N calls.")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--run", action="store_true", help="Call the API. Without it, dry run only."
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    calls = load_calls(args.input_jsonl)
    if args.limit is not None:
        calls = calls[: args.limit]
    template = load_prompt(args.prompt)
    estimate = estimate_cost(calls, template, args.model)
    print(
        "Plan: {requests} request(s) to {model} (effort {effort}); about "
        "{input_tokens:,} input and {output_tokens:,} output tokens; "
        "estimated cost ${cost_usd:.4f}. Largest transcript: "
        "{largest_call_chars:,} characters.".format(
            model=args.model, effort=args.effort, **estimate
        )
    )
    if not args.run:
        print("Dry run only: nothing was sent. Add --run to call the API.")
        return 0
    if Path(args.output_csv).exists() and not args.overwrite:
        raise SystemExit(f"{args.output_csv} exists; pass --overwrite to replace it.")
    check_safety(args, calls)
    rows = run_scoring(args, calls, template)
    write_rows(rows, args.output_csv)
    errors = [row["id"] for row in rows if row["parse_status"] != "ok"]
    tokens_in = sum(row["input_tokens"] or 0 for row in rows)
    tokens_out = sum(row["output_tokens"] or 0 for row in rows)
    price_in, price_out = PRICES_PER_MILLION[args.model]
    actual = tokens_in / 1e6 * price_in + tokens_out / 1e6 * price_out
    print(
        f"Wrote {len(rows)} rows to {args.output_csv}. Parse errors: "
        f"{len(errors)} {errors}. Tokens: {tokens_in:,} in, {tokens_out:,} out; "
        f"cost about ${actual:.4f} at list prices."
    )
    if args.expected_csv:
        scored_ids = {call["id"] for call in calls}
        expected = {
            key: value
            for key, value in read_expected(args.expected_csv).items()
            if key in scored_ids
        }
        report = compare_to_expected(rows, expected)
        print(f"Compared with reference labels for {report['compared']} calls:")
        for field, count in report["agreement"].items():
            print(f"  {field}: {count}/{report['compared']} agree")
        for call_id, field, got, want in report["disagreements"]:
            print(f"  DISAGREE {call_id} {field}: model={got} reference={want}")
        if report["missing_ids"]:
            print(f"  Missing rows: {report['missing_ids']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
