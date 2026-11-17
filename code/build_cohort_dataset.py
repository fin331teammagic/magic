"""Join Gus's Q2 2026 checkpoint files into one event-level cohort file.

Inputs (see docs/GUS_DATA_DICTIONARY.md):
    inputs/q2_2026_events.csv               event list: timing, EPS, sources
    outputs/q2_2026_event_study.csv         CAR[0,1] from easy_es (FF5)
    outputs/q2_2026_financial_features.csv  Run 1 Yahoo variables + statuses

Output:
    outputs/q2_2026_cohort.csv              one row per event_id

This is a pure join: no values are computed, filled, or dropped. Every input
must have unique event_ids, the same event set, and agreeing ticker and
fiscal_period_end, or the script stops with an error.

Run from the repository root:
    python code/build_cohort_dataset.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "inputs" / "q2_2026_events.csv"
EVENT_STUDY = ROOT / "outputs" / "q2_2026_event_study.csv"
FEATURES = ROOT / "outputs" / "q2_2026_financial_features.csv"
OUTPUT = ROOT / "outputs" / "q2_2026_cohort.csv"

KEYS = ["event_id", "ticker", "fiscal_period_end"]


def _check(name: str, frame: pd.DataFrame) -> None:
    missing = [k for k in KEYS if k not in frame.columns]
    if missing:
        raise ValueError("{} is missing key columns: {}".format(name, ", ".join(missing)))
    if frame["event_id"].duplicated().any():
        raise ValueError("{} has duplicate event_id values".format(name))


def build_cohort(events: pd.DataFrame, study: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    for name, frame in [("events", events), ("event study", study), ("features", features)]:
        _check(name, frame)
    ids = set(events["event_id"])
    for name, frame in [("event study", study), ("features", features)]:
        if set(frame["event_id"]) != ids:
            raise ValueError("{} does not cover the same events as the event list".format(name))

    # Columns already in the event list win; others are added with no renaming.
    study_cols = KEYS + [c for c in study.columns if c not in events.columns]
    feature_cols = KEYS + [c for c in features.columns if c not in events.columns and c not in study.columns]
    # Inner joins on all three keys: any ticker / period-end disagreement drops
    # a row, which the length check below turns into an error.
    out = events.merge(study[study_cols], on=KEYS, how="inner", validate="one_to_one")
    out = out.merge(features[feature_cols], on=KEYS, how="inner", validate="one_to_one")
    if len(out) != len(events):
        raise ValueError("ticker / fiscal_period_end disagree across files for {} events".format(
            len(events) - len(out)))
    return out.sort_values(["earnings_timestamp", "event_id"]).reset_index(drop=True)


def main() -> None:
    cohort = build_cohort(pd.read_csv(EVENTS), pd.read_csv(EVENT_STUDY), pd.read_csv(FEATURES))
    cohort.to_csv(OUTPUT, index=False)
    print("Wrote {} ({} events, {} with CAR[0,1], {} in primary timing sample)".format(
        OUTPUT.relative_to(ROOT), len(cohort), int(cohort["car_0_1_pct"].notna().sum()),
        int(cohort["primary_timing_sample"].astype(str).str.lower().eq("true").sum())))


if __name__ == "__main__":
    main()
