# Day 0 vs. earnings-call date (for Gus)

Checked 2026-11-22. The table is in `outputs/q2_2026_day0_transcript_check.csv`,
built from the transcript match (`code/build_transcript_inputs.py`) and
`outputs/q2_2026_cohort.csv`. It has dates only, no transcript text.

**Rule.** For each of the 474 cohort events matched to a Capital IQ earnings
call, compare the call date with the cohort's `day0_session`:
- after-close releases are consistent if the call is on day 0 or the evening
  before;
- other releases are consistent if the call is on day 0.

## Result

| | In Run 1 primary sample | Not in primary | Total |
|---|---|---|---|
| Consistent with the call | 447 | 6 | 453 |
| Day 0 is before the call | 1 | 20 | 21 |

All 21 problem events were matched by fiscal-period end (`matched_by_period_end`).
In each case the cohort's `earnings_timestamp` is an earlier SEC 8-K, not the
quarterly earnings release. Two examples:
- PGR's monthly results;
- operations updates or pre-announcements, for example ABBV, APO and EOG.

The real call is 3 to 27 trading days later. So for these events:
- `day0_session` and `car_0_1_pct` measure the reaction to that earlier
  filing, not to the earnings call;
- 20 of them were already outside the primary sample
  (`primary_timing_sample = False`, mostly `no_yahoo_event`);
- **PGR is the exception.** It is in the primary sample because its
  `timing_check` is `consistent`: Yahoo's date matched the same 8-K. Its
  call was on 2026-08-04, but the cohort's day 0 is 2026-07-15.

## What this changes

- **Run 1 (already run):** 1 of the 426 primary events (PGR) and the 21
  events in the all-events robustness run used the wrong day 0. This is
  disclosed in `specs_tried.md` §8 (Amendment 3). Run 1 is not rerun.
- **Runs 2–3 (not yet run):** `specs_tried.md` Amendment 3 excludes these
  21 events, unless their CAR[0,1] is recomputed with day 0 set from the
  release that goes with the call.

## Gus: optional fix

For each of the 21 events, find the 8-K with the quarterly earnings release.
It is usually filed on the call date or the evening before. Then rerun the
event study for those events with that timestamp.

If that's done before Runs 2–3 are scored, the events come back into the
Run 2–3 sample under Amendment 3.
