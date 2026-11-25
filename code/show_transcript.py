"""Print one call's transcript to your own terminal, for checking LLM scores.

Reads the git-ignored local input built by ``code/build_transcript_inputs.py``
(``restricted_data/llm_inputs/q2_2026_calls.jsonl``). It prints only; it
never writes, copies or sends the text. The transcripts are licensed
Capital IQ data: read them on your computer and never paste them into a
chat, document, issue or AI tool.

    python code/show_transcript.py AAPL_2026-06-27 | less
    python code/show_transcript.py AAPL_2026-06-27 --grep "pricing"
"""

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_INPUT = Path("restricted_data/llm_inputs/q2_2026_calls.jsonl")


def find_call(event_id, path=DEFAULT_INPUT):
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record.get("id") == event_id:
                return record["transcript"]
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("event_id")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--grep", help="Print only paragraphs containing this word or phrase (case-insensitive).")
    args = parser.parse_args(argv)
    if not args.input.exists():
        raise SystemExit(f"{args.input} not found. Put the course transcript files in restricted_data/ and run "
                         "python code/build_transcript_inputs.py first.")
    text = find_call(args.event_id, args.input)
    if text is None:
        raise SystemExit(f"No call with id {args.event_id} in {args.input}.")
    if args.grep:
        pattern = re.compile(re.escape(args.grep), re.IGNORECASE)
        paragraphs = [p for p in re.split(r"\n\s*\n|\n", text) if pattern.search(p)]
        print(f"{len(paragraphs)} paragraph(s) mention '{args.grep}':\n")
        print("\n\n".join(paragraphs))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
