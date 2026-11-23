"""Match the Q2 2026 cohort to licensed transcripts and build the scorer input.

Reads the cohort (``inputs/q2_2026_events.csv``) and the course transcript
files in ``restricted_data/`` (S&P Capital IQ via WRDS, ABF 328 licence), and
writes, inside the git-ignored ``restricted_data/llm_inputs/``:

- ``q2_2026_transcript_match.csv``: one row per cohort event with its match
  status, Capital IQ ``keydevid``, call date and whether the call falls after
  the model training cutoff. No transcript text.
- ``q2_2026_calls.jsonl``: ``{"id": event_id, "transcript": full_text}`` for
  each matched event, the input format of ``code/score_transcripts_edsl.py``.

Matching rule. A cohort event matches a live earnings call (headlines
containing "Pre Recorded" are excluded) for the same firm, by SEC CIK first
and ticker second, whose call date is between one day before and
``--max-lag-days`` after the earnings date (the date of
``earnings_timestamp``). If several calls qualify, the one closest to the
earnings date is used and the event is flagged ``matched_multiple``.
If no call is in that window, the event falls back to the firm's first live
call 1 to 75 days after ``fiscal_period_end`` and is flagged
``matched_by_period_end``: its cohort earnings date (an SEC 8-K acceptance
time) does not match the call date, so its day-0 session should be checked.
Unmatched events are kept in the match file with a reason; they are never
dropped.

Run from the repository root:

    python code/build_transcript_inputs.py
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

DEFAULT_COHORT = Path("inputs/q2_2026_events.csv")
DEFAULT_DATA = Path("restricted_data")
DEFAULT_OUT = Path("restricted_data/llm_inputs")
CALLS_FILE = "calls_sp500_2024_2026.csv"
TEXT_FILE = "call_fulltext_2024_2026.parquet"
# Published training-data cutoff of Claude Haiku/Sonnet/Opus 5.5 (Anthropic
# models overview, retrieved 2026-11-19): June 2026. Calls on or before this
# date may be in the model's training data.
TRAINING_CUTOFF = pd.Timestamp("2026-06-30")
MATCH_COLUMNS = [
    "event_id", "ticker", "fiscal_period_end", "earnings_date", "match_status",
    "match_key", "keydevid", "call_date", "days_from_earnings",
    "n_candidate_calls", "after_training_cutoff", "n_words",
]


def normalize_ticker(value):
    """Upper-case ticker with class separators removed (BF.B -> BFB)."""
    if pd.isna(value):
        return None
    return str(value).upper().replace(".", "").replace("-", "").replace("/", "")


def load_cohort(path):
    cohort = pd.read_csv(path, dtype={"cik": str})
    required = {"event_id", "ticker", "cik", "fiscal_period_end", "earnings_timestamp"}
    missing = required - set(cohort.columns)
    if missing:
        raise ValueError(f"Cohort is missing columns: {sorted(missing)}")
    if cohort["event_id"].duplicated().any():
        raise ValueError("Cohort event_id values are not unique.")
    stamps = pd.to_datetime(cohort["earnings_timestamp"], errors="coerce", utc=False)
    # Timestamps carry their own UTC offsets; the local calendar date is the
    # text before "T".
    cohort["earnings_date"] = pd.to_datetime(
        cohort["earnings_timestamp"].astype(str).str.slice(0, 10), errors="coerce"
    )
    cohort.loc[stamps.isna(), "earnings_date"] = pd.NaT
    cohort["cik_int"] = pd.to_numeric(cohort["cik"], errors="coerce")
    cohort["ticker_norm"] = cohort["ticker"].map(normalize_ticker)
    return cohort


def load_calls(path):
    calls = pd.read_csv(
        path,
        dtype={"gvkey": str, "cik": str},
        usecols=["keydevid", "call_date", "cik", "tic", "headline", "n_words"],
        parse_dates=["call_date"],
    )
    if calls["keydevid"].duplicated().any():
        raise ValueError("keydevid is not unique in the calls file.")
    calls["live"] = ~calls["headline"].str.contains("Pre Recorded", case=False, na=False)
    calls["cik_int"] = pd.to_numeric(calls["cik"], errors="coerce")
    calls["ticker_norm"] = calls["tic"].map(normalize_ticker)
    return calls


def match_events(cohort, calls, max_lag_days, period_fallback_days=75):
    """Return one match row per cohort event (see module docstring)."""
    live = calls[calls["live"]]
    rows = []
    for event in cohort.itertuples(index=False):
        row = {
            "event_id": event.event_id,
            "ticker": event.ticker,
            "fiscal_period_end": event.fiscal_period_end,
            "earnings_date": event.earnings_date.date() if pd.notna(event.earnings_date) else None,
            "match_status": None, "match_key": None, "keydevid": None,
            "call_date": None, "days_from_earnings": None,
            "n_candidate_calls": 0, "after_training_cutoff": None, "n_words": None,
        }
        if pd.isna(event.earnings_date):
            row["match_status"] = "unmatched_no_earnings_date"
            rows.append(row)
            continue
        firm, key = live.iloc[0:0], None
        if pd.notna(event.cik_int):
            firm, key = live[live["cik_int"] == event.cik_int], "cik"
        if firm.empty and event.ticker_norm:
            firm, key = live[live["ticker_norm"] == event.ticker_norm], "ticker"
        if firm.empty:
            row["match_status"] = "unmatched_firm_not_in_transcripts"
            rows.append(row)
            continue
        lag = (firm["call_date"] - event.earnings_date).dt.days
        in_window = (lag >= -1) & (lag <= max_lag_days)
        window = firm[in_window].copy()
        window["lag"] = lag[in_window].to_numpy()
        row["match_key"] = key
        row["n_candidate_calls"] = len(window)
        fallback = False
        if window.empty and pd.notna(event.fiscal_period_end):
            # The cohort's earnings date can be an earlier 8-K (for example a
            # preliminary release). Fall back to the firm's first live call
            # after the fiscal period end and flag the row.
            period_end = pd.Timestamp(event.fiscal_period_end)
            after = (firm["call_date"] - period_end).dt.days
            in_period = (after >= 1) & (after <= period_fallback_days)
            if in_period.any():
                window = firm[in_period].copy()
                window["lag"] = lag[in_period].to_numpy()
                window = window.sort_values(["call_date", "keydevid"]).iloc[[0]]
                fallback = True
        if window.empty:
            last = firm["call_date"].max().date()
            row["match_status"] = (
                "unmatched_after_data_end"
                if event.earnings_date > calls["call_date"].max()
                else f"unmatched_no_call_in_window (latest firm call {last})"
            )
            rows.append(row)
            continue
        best = window.assign(abs_lag=window["lag"].abs()).sort_values(
            ["abs_lag", "call_date", "keydevid"]
        ).iloc[0]
        row.update(
            match_status=(
                "matched_by_period_end" if fallback
                else "matched" if len(window) == 1 else "matched_multiple"
            ),
            keydevid=int(best["keydevid"]),
            call_date=best["call_date"].date(),
            days_from_earnings=int(best["lag"]),
            after_training_cutoff=bool(best["call_date"] > TRAINING_CUTOFF),
            n_words=int(best["n_words"]),
        )
        rows.append(row)
    result = pd.DataFrame(rows, columns=MATCH_COLUMNS)
    matched = result["keydevid"].dropna()
    if matched.duplicated().any():
        raise ValueError("A transcript was matched to more than one cohort event.")
    return result


def write_jsonl(matches, text_path, out_path, after_cutoff_only):
    selected = matches[matches["keydevid"].notna()]
    if after_cutoff_only:
        selected = selected[selected["after_training_cutoff"] == True]  # noqa: E712
    keys = set(selected["keydevid"].astype(int))
    text = pd.read_parquet(text_path, columns=["keydevid", "full_text"])
    text = text[text["keydevid"].isin(keys)].set_index("keydevid")["full_text"]
    missing = keys - set(text.index)
    if missing:
        raise ValueError(f"{len(missing)} matched calls have no full text.")
    with open(out_path, "w", encoding="utf-8") as handle:
        for event in selected.itertuples(index=False):
            body = text.loc[int(event.keydevid)]
            if not isinstance(body, str) or not body.strip():
                raise ValueError(f"Empty transcript for {event.event_id}.")
            handle.write(json.dumps({"id": event.event_id, "transcript": body}) + "\n")
    return len(selected)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cohort", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-lag-days", type=int, default=3)
    parser.add_argument(
        "--after-cutoff-only", action="store_true",
        help="Write only calls held after the June 2026 training cutoff.",
    )
    args = parser.parse_args(argv)

    cohort = load_cohort(args.cohort)
    calls = load_calls(args.data_dir / CALLS_FILE)
    matches = match_events(cohort, calls, args.max_lag_days)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    match_path = args.out_dir / "q2_2026_transcript_match.csv"
    matches.to_csv(match_path, index=False)
    suffix = "_after_cutoff" if args.after_cutoff_only else ""
    jsonl_path = args.out_dir / f"q2_2026_calls{suffix}.jsonl"
    written = write_jsonl(matches, args.data_dir / TEXT_FILE, jsonl_path, args.after_cutoff_only)

    status = matches["match_status"].str.replace(r" \(.*", "", regex=True)
    print(f"Cohort events: {len(matches)}; transcript data ends {calls['call_date'].max().date()}.")
    print(status.value_counts().to_string())
    hit = matches[matches["keydevid"].notna()]
    print(f"Matched calls after the {TRAINING_CUTOFF.date()} training cutoff: "
          f"{int(hit['after_training_cutoff'].sum())} of {len(hit)}.")
    print(f"Wrote {match_path} and {written} transcripts to {jsonl_path}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
