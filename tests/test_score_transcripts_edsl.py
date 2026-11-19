"""Offline tests for the EDSL transcript scorer. No API calls are made."""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from score_transcripts_edsl import (  # noqa: E402
    LOCAL_ONLY_RUN_FLAGS,
    TEMPLATE_VARIABLE,
    VARIABLES,
    compare_to_expected,
    estimate_cost,
    extract_text,
    find_dotenv_files,
    load_calls,
    load_prompt,
    main,
    parse_response,
    read_expected,
)

VALID = {
    "guidance_specificity": 2,
    "guidance_revision": -1,
    "qa_evasiveness": 0,
    "one_off_attribution": 1,
    "analyst_concern_focus": None,
    "status": "scored",
}


class ParseResponseTests(unittest.TestCase):
    def test_valid_json(self):
        parsed = parse_response(json.dumps(VALID))
        self.assertEqual(parsed["parse_status"], "ok")
        for key, value in VALID.items():
            self.assertEqual(parsed[key], value)

    def test_code_fence_is_stripped(self):
        parsed = parse_response("```json\n" + json.dumps(VALID) + "\n```")
        self.assertEqual(parsed["parse_status"], "ok")

    def test_invalid_replies_keep_scores_missing(self):
        bad_replies = [
            None,
            "",
            "The scores are 2, 1, 0.",
            json.dumps([1, 2]),
            json.dumps({**VALID, "explanation": "x"}),
            json.dumps({k: v for k, v in VALID.items() if k != "qa_evasiveness"}),
            json.dumps({**VALID, "guidance_revision": 2}),
            json.dumps({**VALID, "qa_evasiveness": True}),
            json.dumps({**VALID, "qa_evasiveness": 1.0}),
            json.dumps({**VALID, "status": "insufficient_outlook"}),
            json.dumps({**VALID, "status": "incomplete_transcript"}),
            "“guidance_specificity”: 2",
        ]
        for reply in bad_replies:
            with self.subTest(reply=reply):
                parsed = parse_response(reply)
                self.assertEqual(parsed["parse_status"], "error")
                self.assertTrue(parsed["parse_error"])
                for name in VARIABLES:
                    self.assertIsNone(parsed[name])

    def test_incomplete_transcript_all_null(self):
        reply = {name: None for name in VARIABLES} | {"status": "incomplete_transcript"}
        parsed = parse_response(json.dumps(reply))
        self.assertEqual(parsed["parse_status"], "ok")
        self.assertEqual(parsed["status"], "incomplete_transcript")


class ExtractTextTests(unittest.TestCase):
    def test_skips_thinking_blocks(self):
        raw = {
            "content": [
                {"type": "thinking", "thinking": ""},
                {"type": "text", "text": '{"a": 1}'},
            ]
        }
        self.assertEqual(extract_text(raw, fallback="other"), '{"a": 1}')

    def test_falls_back_without_content(self):
        self.assertEqual(extract_text({"message": []}, fallback="x"), "x")
        self.assertEqual(extract_text(None, fallback="x"), "x")


class InputTests(unittest.TestCase):
    def test_load_calls_rejects_duplicates_and_blanks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calls.jsonl"
            path.write_text(
                '{"id": "SYN-1", "transcript": "a"}\n{"id": "SYN-1", "transcript": "b"}\n'
            )
            with self.assertRaises(ValueError):
                load_calls(path)
            path.write_text('{"id": "SYN-1", "transcript": "  "}\n')
            with self.assertRaises(ValueError):
                load_calls(path)

    def test_prompt_needs_one_transcript_variable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prompt.txt"
            path.write_text("no variable here")
            with self.assertRaises(ValueError):
                load_prompt(path)
            path.write_text(f"A {TEMPLATE_VARIABLE} B")
            self.assertIn(TEMPLATE_VARIABLE, load_prompt(path))

    def test_committed_prompt_and_synthetic_sets_are_consistent(self):
        template = load_prompt(ROOT / "prompts" / "transcript_llm_scores_v2.0.txt")
        for name in VARIABLES:
            self.assertIn(name, template)
        for stem in ("development", "validation"):
            calls = load_calls(ROOT / "inputs" / f"synthetic_v2_{stem}.jsonl")
            expected = read_expected(ROOT / "inputs" / f"synthetic_v2_{stem}_expected.csv")
            self.assertEqual({call["id"] for call in calls}, set(expected))
            self.assertTrue(all(call["id"].startswith("SYN") for call in calls))


class SafetyAndCostTests(unittest.TestCase):
    def test_local_only_flags(self):
        self.assertEqual(
            LOCAL_ONLY_RUN_FLAGS,
            {
                "disable_remote_inference": True,
                "disable_remote_cache": True,
                "offload_execution": False,
                "use_api_proxy": False,
            },
        )

    def test_find_dotenv_files_checks_parents(self):
        with tempfile.TemporaryDirectory() as tmp:
            child = Path(tmp) / "a" / "b"
            child.mkdir(parents=True)
            self.assertEqual(
                [p for p in find_dotenv_files([child]) if p.startswith(str(Path(tmp).resolve()))],
                [],
            )
            (Path(tmp) / "a" / ".env").write_text("")
            found = find_dotenv_files([child])
            self.assertIn(str((Path(tmp) / "a" / ".env").resolve()), found)

    def test_estimate_cost(self):
        calls = [{"id": "SYN-1", "transcript": "x" * 3500}]
        template = f"{TEMPLATE_VARIABLE}"
        estimate = estimate_cost(calls, template, "claude-sonnet-5-5")
        self.assertEqual(estimate["requests"], 1)
        self.assertEqual(estimate["input_tokens"], 1000)
        self.assertAlmostEqual(estimate["cost_usd"], 1000 / 1e6 * 2 + 80 / 1e6 * 10)

    def test_dry_run_sends_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out.csv"
            code = main(
                [
                    "--input-jsonl", str(ROOT / "inputs" / "synthetic_v2_development.jsonl"),
                    "--prompt", str(ROOT / "prompts" / "transcript_llm_scores_v2.0.txt"),
                    "--prompt-version", "2.0",
                    "--model", "claude-sonnet-5-5",
                    "--output-csv", str(output),
                ]
            )
            self.assertEqual(code, 0)
            self.assertFalse(output.exists())


class CompareTests(unittest.TestCase):
    def test_compare_counts_disagreements_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "expected.csv"
            with open(path, "w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", *VARIABLES, "status", "note"])
                writer.writerow(["A", 2, -1, 0, 1, "null", "scored", ""])
                writer.writerow(["B", 0, "null", "null", 0, "null", "scored", ""])
            rows = [{"id": "A"} | VALID | {"qa_evasiveness": 1}]
            report = compare_to_expected(rows, read_expected(path))
        self.assertEqual(report["compared"], 1)
        self.assertEqual(report["agreement"]["qa_evasiveness"], 0)
        self.assertEqual(report["agreement"]["guidance_specificity"], 1)
        self.assertEqual(report["missing_ids"], ["B"])
        self.assertEqual(len(report["disagreements"]), 1)


if __name__ == "__main__":
    unittest.main()
