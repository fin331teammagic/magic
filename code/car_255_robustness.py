"""Amendment 4 robustness: CAR[0,1] with a true 255-session estimation window.

easy_es (the primary outcome, ``car_0_1_pct``) estimates the FF5 model over
trading-day offsets -315 to -61 before day 0, but it first expands each event
by *calendar* days, so only about 164 of those 255 sessions exist
(``docs/GUS_DATA_DICTIONARY.md``). This script applies easy_es's exact model
on the full window:

- y = daily return (Adj Close percent change, as easy_es builds it);
  x = Mkt-RF, SMB, HML, RMW, CMA (Kenneth French daily, as fractions) plus a
  constant; OLS; at least 100 estimation days with factor data.
- AR = return - fitted return; CAR[0,1] = AR(day 0) + AR(day 1), in percent.
- Offsets are counted over the stock's trading days. ``--mode easy_es``
  truncates the history the way easy_es does, to check that this code
  reproduces the committed ``car_0_1_pct``; ``--mode full`` is the robustness
  outcome.

Prices and factors come from the same cached loaders as ``gus_collect.py``
(``data/raw/``, git-ignored). Writes ``outputs/q2_2026_car_255.csv``.

    python code/car_255_robustness.py --mode easy_es   # check
    python code/car_255_robustness.py --mode full      # robustness outcome
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gus_collect as gc  # noqa: E402

FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]
EST_LO, EST_HI = -(10 + 50 + 255), -(10 + 50) - 1  # easy_es estimation offsets
CALENDAR_BEFORE, CALENDAR_AFTER = 10 + 50 + 255 + 10, 10 + 10  # easy_es expansion
MIN_ESTIMATION_DAYS = 100
AS_OF = "2026-11-13"


def car_0_1(returns, factors, day0, mode):
    """CAR[0,1] in percent for one event, plus the estimation-day count.

    ``returns``: Series of daily returns indexed by date (trading days with a
    return). ``factors``: DataFrame indexed by date with FACTORS.
    """
    day0 = pd.Timestamp(day0)
    dates = returns.index
    if mode == "easy_es":
        keep = (dates >= day0 - pd.Timedelta(days=CALENDAR_BEFORE)) & (dates <= day0 + pd.Timedelta(days=CALENDAR_AFTER))
        returns = returns[keep]
        dates = returns.index
    if day0 not in dates:
        return np.nan, 0
    offsets = pd.Series(np.arange(len(dates)) - dates.get_loc(day0), index=dates)
    frame = pd.DataFrame({"ret": returns, "offset": offsets}).join(factors, how="inner")
    est = frame[(frame["offset"] >= EST_LO) & (frame["offset"] <= EST_HI)]
    if len(est) < MIN_ESTIMATION_DAYS:
        return np.nan, len(est)
    x = np.column_stack([np.ones(len(est)), est[FACTORS].to_numpy()])
    beta, *_ = np.linalg.lstsq(x, est["ret"].to_numpy(), rcond=None)
    window = frame[frame["offset"].isin([0, 1])]
    if len(window) < 2:
        return np.nan, len(est)
    fitted = np.column_stack([np.ones(2), window[FACTORS].to_numpy()]) @ beta
    return float(100 * (window["ret"].to_numpy() - fitted).sum()), len(est)


def load_inputs(cohort):
    returns = gc.easy_es_returns(cohort["yahoo_symbol"].dropna().unique(), AS_OF)
    returns["Date"] = pd.to_datetime(returns["Date"])
    ff5, vintage = gc.french_ff5()
    ff5 = ff5.assign(Date=pd.to_datetime(ff5["Date"])).set_index("Date")[FACTORS]
    by_ticker = {t: g.set_index("Date")["Ret"].sort_index() for t, g in returns.groupby("ticker")}
    return by_ticker, ff5, vintage


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--mode", choices=["easy_es", "full"], default="full")
    parser.add_argument("--cohort", type=Path, default=Path("outputs/q2_2026_cohort.csv"))
    parser.add_argument("--out", type=Path, default=Path("outputs/q2_2026_car_255.csv"))
    args = parser.parse_args(argv)

    cohort = pd.read_csv(args.cohort)
    by_ticker, ff5, vintage = load_inputs(cohort)
    rows = []
    for event in cohort.itertuples():
        series = by_ticker.get(event.yahoo_symbol)
        car, nobs = (np.nan, 0)
        if series is not None and isinstance(event.day0_session, str):
            car, nobs = car_0_1(series, ff5, event.day0_session, args.mode)
        rows.append({"event_id": event.event_id, "car_0_1_pct_committed": event.car_0_1_pct,
                     "car_0_1_pct_recomputed": car, "estimation_nobs_recomputed": nobs})
    out = pd.DataFrame(rows)
    both = out.dropna(subset=["car_0_1_pct_committed", "car_0_1_pct_recomputed"])
    diff = (both["car_0_1_pct_recomputed"] - both["car_0_1_pct_committed"]).abs()
    print(f"mode={args.mode} | factors: {vintage} | events with both: {len(both)}")
    print(f"estimation days: median {out['estimation_nobs_recomputed'].median():.0f}")
    print(f"|recomputed - committed| pp: median {diff.median():.6f}, max {diff.max():.4f}, "
          f"corr {both[['car_0_1_pct_recomputed', 'car_0_1_pct_committed']].corr().iloc[0, 1]:.5f}")
    if args.mode == "full":
        out = out.rename(columns={"car_0_1_pct_recomputed": "car_0_1_pct_255",
                                  "estimation_nobs_recomputed": "estimation_nobs_255"})
        out["car_255_model"] = ("FF5 OLS (easy_es model), estimation offsets [-315,-61] over full trading "
                                f"history, min {MIN_ESTIMATION_DAYS} days; prices Yahoo Adj Close as of {AS_OF}")
        out["factor_source"] = "Kenneth French Data Library, Fama/French 5 Factors (2x3) daily; " + vintage
        out["data_status"] = "cohort"
        out.to_csv(args.out, index=False)
        print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
