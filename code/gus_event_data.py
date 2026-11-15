"""Pure, offline logic for Gus's event list, CAR[0,1], and financial features.

Nothing in this module downloads data. The collector in `gus_collect.py`
fetches source data and passes it here, so every rule below is unit tested
without network access.

Conventions (see docs/GUS_DATA_DICTIONARY.md):
- One row per company-quarter event, keyed by `event_id` =
  "{TICKER}_{fiscal_period_end}" (e.g. "MSFT_2026-06-30").
- Day 0 follows the repository rule in `pead_pipeline.py`: an announcement at
  or after 16:00 America/New_York maps to the next trading session; any
  earlier time maps to the first session on or after the announcement date.
- Financial features use only information dated strictly before day 0.
- Missing values stay missing (blank in CSV), with a reason in
  `<feature>_status`. They are never filled with zero.
"""

from datetime import time

import numpy as np
import pandas as pd

EASTERN = "America/New_York"
Q2_2026_START = pd.Timestamp("2026-04-01")
Q2_2026_END = pd.Timestamp("2026-06-30")

# Dual share classes hold one earnings call; keep the class A listing.
SECONDARY_SHARE_CLASSES = {"GOOG": "GOOGL", "FOX": "FOXA", "NWS": "NWSA"}

PERIODIC_FORMS = ("10-Q", "10-K")
EARNINGS_ITEM = "2.02"

STATUS_OBSERVED = "observed"
STATUS_UNAVAILABLE = "missing_unavailable"
STATUS_NOT_PIT = "missing_not_point_in_time"
STATUS_CURRENT_ONLY = "excluded_current_only"
# A value is present but rests on Yahoo's consensus EPS, which is not a
# preserved point-in-time record. Treat as unverified, not as confirmed.
STATUS_OBSERVED_CONSENSUS_NOT_PIT = "observed_consensus_not_pit"
VALUE_STATUSES = (STATUS_OBSERVED, STATUS_OBSERVED_CONSENSUS_NOT_PIT, STATUS_UNAVAILABLE, STATUS_NOT_PIT, STATUS_CURRENT_ONLY)
VALUE_PRESENT_STATUSES = (STATUS_OBSERVED, STATUS_OBSERVED_CONSENSUS_NOT_PIT)
YAHOO_ONLY_TIMING = "yahoo_only_no_sec_8k"

# Cammy's Run 1 variables (ANALYSIS_PLAN.md) and how each is measured.
FEATURE_SPEC = {
    "eps_surprise_usd": ("USD per share", "eps_actual - eps_estimate"),
    "eps_surprise_pct": ("percent", "(eps_actual - eps_estimate) / abs(eps_estimate) * 100"),
    "log_market_cap": ("ln(USD)", "ln(unadjusted close on day -1 * latest shares outstanding dated before day 0)"),
    "price_to_book": ("ratio", "market cap / prior-quarter stockholders' equity; missing if equity <= 0"),
    "forward_pe": ("ratio", "Yahoo provides only a current snapshot; not used"),
    "profit_margin_pct": ("percent", "prior-quarter net income / prior-quarter total revenue * 100"),
    "revenue_growth_yoy_pct": ("percent", "prior-quarter revenue / same quarter one year earlier - 1, * 100"),
    "earnings_growth_yoy_pct": ("percent", "prior-quarter net income / same quarter one year earlier - 1, * 100; missing if base <= 0"),
    "debt_to_equity": ("ratio", "prior-quarter total debt / stockholders' equity; missing if equity <= 0"),
    "beta_252d": ("ratio", "OLS slope of daily stock return on SPY return, 252 sessions ending day -1 (min 200)"),
    "return_52w_pct": ("percent", "adjusted close day -1 / adjusted close 252 sessions earlier - 1, * 100"),
    "ma50_ma200_gap_pct": ("percent", "(50-session mean - 200-session mean) / 200-session mean of adjusted close * 100"),
    "avg_daily_volume_63d": ("shares", "mean daily volume over the 63 sessions ending day -1"),
    "short_interest_pct_float": ("percent", "Yahoo provides only a current snapshot; not used"),
}
CURRENT_ONLY_FEATURES = ("forward_pe", "short_interest_pct_float")


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------

def make_event_id(ticker, fiscal_period_end):
    """Return the shared join key, e.g. 'BRK.B_2026-06-30'."""
    ticker = str(ticker).strip().upper()
    if not ticker:
        raise ValueError("Ticker is empty.")
    period = pd.Timestamp(fiscal_period_end).strftime("%Y-%m-%d")
    return "{}_{}".format(ticker, period)


def yahoo_symbol(ticker):
    """Yahoo spells share classes with a hyphen (BRK.B -> BRK-B)."""
    return str(ticker).strip().upper().replace(".", "-")


def in_q2_2026(fiscal_period_end):
    period = pd.Timestamp(fiscal_period_end).normalize()
    return Q2_2026_START <= period <= Q2_2026_END


# --------------------------------------------------------------------------
# Timing
# --------------------------------------------------------------------------

def to_eastern(timestamp):
    """Convert a timezone-aware timestamp to New York time; reject naive ones."""
    stamp = pd.Timestamp(timestamp)
    if stamp.tzinfo is None:
        raise ValueError("Timestamp {} has no timezone.".format(timestamp))
    return stamp.tz_convert(EASTERN)


def assign_day0_session(timestamp, sessions):
    """Map an announcement timestamp to its first tradable session (day 0).

    `sessions` is an iterable of trading dates. Returns NaT when the session
    falls after the last available date.
    """
    local = to_eastern(timestamp)
    sessions = pd.DatetimeIndex(pd.to_datetime(list(sessions))).normalize().unique().sort_values()
    day = pd.Timestamp(local.date())
    after_close = local.time() >= time(16, 0)
    position = sessions.searchsorted(day, side="right" if after_close else "left")
    if position >= len(sessions):
        return pd.NaT
    return sessions[position]


def release_timing(timestamp):
    local = to_eastern(timestamp).time()
    if local < time(9, 30):
        return "pre_market"
    if local < time(16, 0):
        return "during_market"
    return "after_close"


# --------------------------------------------------------------------------
# EDGAR filing selection
# --------------------------------------------------------------------------

def _prepare_filings(filings):
    frame = filings.copy()
    frame["reportDate"] = pd.to_datetime(frame["reportDate"].replace("", np.nan), errors="coerce")
    frame["filingDate"] = pd.to_datetime(frame["filingDate"], errors="coerce")
    frame["acceptanceDateTime"] = pd.to_datetime(frame["acceptanceDateTime"], utc=True, errors="coerce")
    frame["items"] = frame.get("items", "").fillna("").astype(str)
    return frame


def select_q2_periodic_filings(filings):
    """Return original 10-Q/10-K filings whose period ends in calendar Q2 2026."""
    frame = _prepare_filings(filings)
    mask = frame["form"].isin(PERIODIC_FORMS) & frame["reportDate"].between(Q2_2026_START, Q2_2026_END)
    return frame.loc[mask].sort_values("reportDate")


def find_earnings_release(filings, fiscal_period_end, periodic_filing_date, max_lag_days=7):
    """First 8-K with Item 2.02 after the period end and before the periodic filing.

    The 8-K may follow the 10-Q/10-K by up to `max_lag_days`. Returns a Series
    or None.
    """
    frame = _prepare_filings(filings)
    period = pd.Timestamp(fiscal_period_end)
    latest = pd.Timestamp(periodic_filing_date) + pd.Timedelta(days=max_lag_days)
    is_release = frame["form"].eq("8-K") & frame["items"].str.contains(EARNINGS_ITEM, regex=False)
    window = frame["filingDate"].gt(period) & frame["filingDate"].le(latest)
    candidates = frame.loc[is_release & window].sort_values("acceptanceDateTime")
    if candidates.empty:
        return None
    return candidates.iloc[0]


def prior_quarter_filing(filings, fiscal_period_end, max_gap_days=130):
    """Latest 10-Q/10-K for the quarter before the event quarter, or None."""
    frame = _prepare_filings(filings)
    period = pd.Timestamp(fiscal_period_end)
    mask = (
        frame["form"].isin(PERIODIC_FORMS)
        & frame["reportDate"].lt(period - pd.Timedelta(days=30))
        & frame["reportDate"].ge(period - pd.Timedelta(days=max_gap_days))
    )
    candidates = frame.loc[mask].sort_values(["reportDate", "filingDate"])
    if candidates.empty:
        return None
    return candidates.iloc[-1]


# --------------------------------------------------------------------------
# Yahoo cross-check
# --------------------------------------------------------------------------

def match_yahoo_event(yahoo_events, edgar_day0, sessions, max_days=5):
    """Find the Yahoo earnings row nearest the EDGAR day 0.

    `yahoo_events` has a timezone-aware DatetimeIndex and the yfinance columns
    'EPS Estimate' and 'Reported EPS'. Returns a dict with the Yahoo
    timestamp, its day 0, EPS values, and a timing check label.
    """
    empty = {
        "yahoo_timestamp": pd.NaT,
        "yahoo_day0_session": pd.NaT,
        "eps_actual": np.nan,
        "eps_estimate": np.nan,
        "timing_check": "no_yahoo_event",
    }
    if yahoo_events is None or len(yahoo_events) == 0 or pd.isna(edgar_day0):
        return empty
    index = pd.DatetimeIndex(yahoo_events.index)
    if index.tz is None:
        raise ValueError("Yahoo earnings dates must be timezone-aware.")
    local_dates = index.tz_convert(EASTERN).normalize().tz_localize(None)
    gaps = np.abs((local_dates - pd.Timestamp(edgar_day0)).days)
    if gaps.min() > max_days:
        return empty
    position = int(np.argmin(gaps))
    row = yahoo_events.iloc[position]
    yahoo_day0 = assign_day0_session(index[position], sessions)
    return {
        "yahoo_timestamp": index[position],
        "yahoo_day0_session": yahoo_day0,
        "eps_actual": pd.to_numeric(row.get("Reported EPS"), errors="coerce"),
        "eps_estimate": pd.to_numeric(row.get("EPS Estimate"), errors="coerce"),
        "timing_check": "consistent" if yahoo_day0 == pd.Timestamp(edgar_day0) else "yahoo_day0_differs",
    }


def yahoo_release_after_period(yahoo_events, fiscal_period_end, latest_date):
    """Fallback when no SEC 8-K Item 2.02 exists: the first Yahoo earnings
    event dated after the period end and no later than `latest_date`
    (New York dates). Returns (timestamp, row) or None. Single-source timing.
    """
    if yahoo_events is None or len(yahoo_events) == 0:
        return None
    index = pd.DatetimeIndex(yahoo_events.index)
    if index.tz is None:
        raise ValueError("Yahoo earnings dates must be timezone-aware.")
    dates = index.tz_convert(EASTERN).normalize().tz_localize(None)
    mask = (dates > pd.Timestamp(fiscal_period_end)) & (dates <= pd.Timestamp(latest_date))
    if not mask.any():
        return None
    position = int(np.flatnonzero(mask)[np.argmin(dates[mask])])
    return index[position], yahoo_events.iloc[position]


def eps_surprise(actual, estimate):
    """Return (surprise in USD, surprise in percent); NaN when undefined."""
    if pd.isna(actual) or pd.isna(estimate):
        return np.nan, np.nan
    usd = float(actual) - float(estimate)
    pct = np.nan if float(estimate) == 0 else usd / abs(float(estimate)) * 100
    return usd, pct


# --------------------------------------------------------------------------
# Event study (easy_es) post-processing
# --------------------------------------------------------------------------

def easy_es_input(manifest):
    """Events for easy_es: Yahoo symbol and day-0 session as `event_date`."""
    frame = manifest.dropna(subset=["day0_session"])
    events = pd.DataFrame(
        {
            "ticker": frame["yahoo_symbol"].astype(str),
            "event_date": pd.to_datetime(frame["day0_session"]).dt.strftime("%Y-%m-%d"),
            "event_id": frame["event_id"].astype(str),
        }
    ).reset_index(drop=True)
    if events.duplicated(["ticker", "event_date"]).any():
        raise ValueError("Duplicate ticker/day-0 pairs would be ambiguous in easy_es.")
    return events


def car_0_1_from_easy_es(results, events):
    """Compute CAR[0,1] = AR(day 0) + AR(day 1) in percent for each event.

    easy_es's own `car` column cumulates from the start of its window
    (day -10 by default), so it is not CAR[0,1]. easy_es also renumbers
    events; rows are matched back on (ticker, event_date). Events with a
    missing day 0 or day 1 abnormal return get a blank value and a status.
    """
    out = events[["event_id", "ticker", "event_date"]].copy()
    out["car_0_1_pct"] = np.nan
    out["ar_day0_pct"] = np.nan
    out["ar_day1_pct"] = np.nan
    out["estimation_resid_std"] = np.nan
    out["car_0_1_status"] = "dropped_by_package"
    if results is None or len(results) == 0:
        return out.drop(columns=["ticker", "event_date"])

    res = results.copy()
    res["event_date"] = pd.to_datetime(res["event_date"]).dt.strftime("%Y-%m-%d")
    res = res[res["Offset"].isin([0, 1])]
    if res.duplicated(["ticker", "event_date", "Offset"]).any():
        raise ValueError("easy_es output has duplicate rows for an event day.")
    wide = res.pivot(index=["ticker", "event_date"], columns="Offset", values="ar")
    std = res.groupby(["ticker", "event_date"])["estimation_std"].first()
    for position, row in out.iterrows():
        key = (row["ticker"], row["event_date"])
        if key not in std.index:
            continue
        ar0 = wide.at[key, 0] if 0 in wide.columns else np.nan
        ar1 = wide.at[key, 1] if 1 in wide.columns else np.nan
        out.at[position, "estimation_resid_std"] = std.loc[key]
        out.at[position, "ar_day0_pct"] = ar0 * 100 if pd.notna(ar0) else np.nan
        out.at[position, "ar_day1_pct"] = ar1 * 100 if pd.notna(ar1) else np.nan
        if pd.notna(ar0) and pd.notna(ar1):
            out.at[position, "car_0_1_pct"] = (ar0 + ar1) * 100
            out.at[position, "car_0_1_status"] = "complete"
        else:
            out.at[position, "car_0_1_status"] = "missing_day0_or_day1"
    return out.drop(columns=["ticker", "event_date"])


def easy_es_estimation_nobs(return_dates, factor_dates, day0, estimation_days=255, gap_days=50,
                            window_before=10, window_after=10, aux_offset=10):
    """Replicate easy_es's estimation-window count for one event.

    easy_es expands each event by calendar days (window_before + gap_days +
    estimation_days + 10 before day 0), numbers the trading days that have a
    stock return, then keeps estimation offsets
    [-(window_before + gap_days + estimation_days), -(window_before + gap_days) - 1]
    that also have factor data. Its output omits these rows, so count them here.
    """
    day0 = pd.Timestamp(day0).normalize()
    lower = day0 - pd.Timedelta(days=window_before + gap_days + estimation_days + aux_offset)
    upper = day0 + pd.Timedelta(days=window_after + aux_offset)
    dates = pd.DatetimeIndex(pd.to_datetime(list(return_dates))).normalize().unique().sort_values()
    dates = dates[(dates >= lower) & (dates <= upper)]
    if day0 not in dates:
        return np.nan
    offsets = np.arange(len(dates)) - dates.get_loc(day0)
    lo, hi = -(window_before + gap_days + estimation_days), -(window_before + gap_days) - 1
    factors = set(pd.DatetimeIndex(pd.to_datetime(list(factor_dates))).normalize())
    return int(sum(1 for d, o in zip(dates, offsets) if lo <= o <= hi and d in factors))


# --------------------------------------------------------------------------
# Financial features (point in time)
# --------------------------------------------------------------------------

def _value(name, value, status, source_field, known_by=pd.NaT, source_period_end=pd.NaT, note=""):
    if status not in VALUE_PRESENT_STATUSES or value is None or (isinstance(value, float) and not np.isfinite(value)):
        if status in VALUE_PRESENT_STATUSES:
            status = STATUS_UNAVAILABLE
        value = np.nan
    return {
        "variable": name,
        "value": value,
        "value_status": status,
        "source_field": source_field,
        "source_period_end": source_period_end,
        "known_by_date": known_by,
        "note": note,
    }


def pre_event_window(series, day0):
    """Rows strictly before day 0 (the information available on day -1)."""
    index = pd.DatetimeIndex(pd.to_datetime(series.index))
    if index.tz is not None:
        index = index.tz_convert(EASTERN).tz_localize(None)
    clean = series.copy()
    clean.index = index.normalize()
    clean = clean[~clean.index.duplicated(keep="last")].sort_index()
    return clean[clean.index < pd.Timestamp(day0)].dropna()


def price_features(prices, benchmark_adj_close, day0):
    """Momentum, beta, volume, and the day -1 close from data before day 0.

    `prices` has columns 'Adj Close', 'Close', 'Volume' indexed by date.
    """
    rows = []
    adj = pre_event_window(prices["Adj Close"], day0)
    vol = pre_event_window(prices["Volume"], day0)
    close = pre_event_window(prices["Close"], day0)
    last_date = adj.index[-1] if len(adj) else pd.NaT

    if len(adj) >= 253:
        value = (adj.iloc[-1] / adj.iloc[-253] - 1) * 100
        rows.append(_value("return_52w_pct", value, STATUS_OBSERVED, "Adj Close", last_date))
    else:
        rows.append(_value("return_52w_pct", None, STATUS_UNAVAILABLE, "Adj Close", note="fewer than 253 sessions before day 0"))

    if len(adj) >= 200:
        ma50, ma200 = adj.iloc[-50:].mean(), adj.iloc[-200:].mean()
        rows.append(_value("ma50_ma200_gap_pct", (ma50 - ma200) / ma200 * 100, STATUS_OBSERVED, "Adj Close", last_date))
    else:
        rows.append(_value("ma50_ma200_gap_pct", None, STATUS_UNAVAILABLE, "Adj Close", note="fewer than 200 sessions before day 0"))

    if len(vol) >= 63:
        rows.append(_value("avg_daily_volume_63d", float(vol.iloc[-63:].mean()), STATUS_OBSERVED, "Volume", last_date))
    else:
        rows.append(_value("avg_daily_volume_63d", None, STATUS_UNAVAILABLE, "Volume", note="fewer than 63 sessions before day 0"))

    bench = pre_event_window(benchmark_adj_close, day0)
    joined = pd.concat([adj.rename("s"), bench.rename("m")], axis=1, join="inner").pct_change(fill_method=None).dropna().iloc[-252:]
    if len(joined) >= 200 and joined["m"].var() > 0:
        beta = np.cov(joined["s"], joined["m"], ddof=1)[0, 1] / joined["m"].var(ddof=1)
        rows.append(_value("beta_252d", beta, STATUS_OBSERVED, "Adj Close vs SPY Adj Close", last_date, note="{} returns".format(len(joined))))
    else:
        rows.append(_value("beta_252d", None, STATUS_UNAVAILABLE, "Adj Close vs SPY Adj Close", note="fewer than 200 overlapping returns"))

    close_value = float(close.iloc[-1]) if len(close) else np.nan
    close_date = close.index[-1] if len(close) else pd.NaT
    return rows, close_value, close_date


def unadjusted_close(split_adjusted_close, close_date, splits):
    """Undo splits dated after `close_date` (yfinance 'Close' is split-adjusted)."""
    if pd.isna(split_adjusted_close):
        return np.nan
    if splits is None or len(splits) == 0:
        return split_adjusted_close
    index = pd.DatetimeIndex(pd.to_datetime(splits.index))
    if index.tz is not None:
        index = index.tz_convert(EASTERN).tz_localize(None)
    later = pd.Series(splits.to_numpy(dtype=float), index=index.normalize())
    later = later[(later.index > pd.Timestamp(close_date)) & (later > 0)]
    return split_adjusted_close * float(np.prod(later.to_numpy())) if len(later) else split_adjusted_close


def latest_before(series, day0, max_age_days=200):
    """Last value dated strictly before day 0 and no older than max_age_days."""
    window = pre_event_window(series, day0)
    if window.empty:
        return np.nan, pd.NaT
    date = window.index[-1]
    if (pd.Timestamp(day0) - date).days > max_age_days:
        return np.nan, pd.NaT
    return float(window.iloc[-1]), date


def _statement_value(statement, field, period_end, tolerance_days=10):
    """Value for a statement row at a period end (within tolerance)."""
    if statement is None or statement.empty or field not in statement.index:
        return np.nan, pd.NaT
    columns = pd.DatetimeIndex(pd.to_datetime(statement.columns)).normalize()
    gaps = np.abs((columns - pd.Timestamp(period_end)).days)
    if len(gaps) == 0 or gaps.min() > tolerance_days:
        return np.nan, pd.NaT
    position = int(np.argmin(gaps))
    value = pd.to_numeric(statement.loc[field].iloc[position], errors="coerce")
    return (float(value) if pd.notna(value) else np.nan), columns[position]


def _first_field(statement, fields, period_end):
    for field in fields:
        value, column = _statement_value(statement, field, period_end)
        if pd.notna(value):
            return value, column, field
    return np.nan, pd.NaT, fields[0]


def statement_features(income, balance, prior_period_end, prior_filing_date, day0, market_cap):
    """Prior-quarter fundamentals, usable only if that filing predates day 0.

    `income` and `balance` are yfinance quarterly statements (rows = fields,
    columns = period ends). The prior quarter was reported before the call;
    the event quarter's own figures are released at the call and are not used.
    """
    names = ["price_to_book", "profit_margin_pct", "revenue_growth_yoy_pct", "earnings_growth_yoy_pct", "debt_to_equity"]
    if pd.isna(prior_period_end) or pd.isna(prior_filing_date):
        return [_value(n, None, STATUS_NOT_PIT, "", note="prior-quarter filing date not verified") for n in names]
    if pd.Timestamp(prior_filing_date) >= pd.Timestamp(day0):
        return [_value(n, None, STATUS_NOT_PIT, "", prior_filing_date, prior_period_end, "prior-quarter filing not before day 0") for n in names]

    known, period = pd.Timestamp(prior_filing_date), pd.Timestamp(prior_period_end)
    equity, eq_col, eq_field = _first_field(balance, ["Stockholders Equity", "Common Stock Equity"], period)
    debt, _, debt_field = _first_field(balance, ["Total Debt"], period)
    revenue, rev_col, rev_field = _first_field(income, ["Total Revenue", "Operating Revenue"], period)
    income_value, _, ni_field = _first_field(income, ["Net Income", "Net Income Common Stockholders"], period)
    year_ago = period - pd.Timedelta(days=364)
    revenue_ago, _, _ = _first_field(income, [rev_field], year_ago)
    income_ago, _, _ = _first_field(income, [ni_field], year_ago)

    rows = []
    if pd.notna(market_cap) and pd.notna(equity) and equity > 0:
        rows.append(_value("price_to_book", market_cap / equity, STATUS_OBSERVED, eq_field, known, period))
    else:
        rows.append(_value("price_to_book", None, STATUS_UNAVAILABLE, eq_field, known, period, "missing market cap or equity <= 0"))

    if pd.notna(revenue) and revenue != 0 and pd.notna(income_value):
        rows.append(_value("profit_margin_pct", income_value / revenue * 100, STATUS_OBSERVED, "{}/{}".format(ni_field, rev_field), known, period))
    else:
        rows.append(_value("profit_margin_pct", None, STATUS_UNAVAILABLE, "{}/{}".format(ni_field, rev_field), known, period, "missing or zero revenue"))

    if pd.notna(revenue) and pd.notna(revenue_ago) and revenue_ago > 0:
        rows.append(_value("revenue_growth_yoy_pct", (revenue / revenue_ago - 1) * 100, STATUS_OBSERVED, rev_field, known, period))
    else:
        rows.append(_value("revenue_growth_yoy_pct", None, STATUS_UNAVAILABLE, rev_field, known, period, "year-ago quarter not in Yahoo history"))

    if pd.notna(income_value) and pd.notna(income_ago) and income_ago > 0:
        rows.append(_value("earnings_growth_yoy_pct", (income_value / income_ago - 1) * 100, STATUS_OBSERVED, ni_field, known, period))
    else:
        rows.append(_value("earnings_growth_yoy_pct", None, STATUS_UNAVAILABLE, ni_field, known, period, "year-ago quarter missing or base <= 0"))

    if pd.notna(debt) and pd.notna(equity) and equity > 0:
        rows.append(_value("debt_to_equity", debt / equity, STATUS_OBSERVED, "{}/{}".format(debt_field, eq_field), known, period))
    else:
        rows.append(_value("debt_to_equity", None, STATUS_UNAVAILABLE, "{}/{}".format(debt_field, eq_field), known, period, "missing debt or equity <= 0"))
    return rows


def current_only_rows():
    return [_value(name, None, STATUS_CURRENT_ONLY, "Yahoo info snapshot", note="no verifiable history before the call") for name in CURRENT_ONLY_FEATURES]


def wide_features(provenance):
    """Pivot long provenance rows to one row per event with value and status columns."""
    values = provenance.pivot(index="event_id", columns="variable", values="value")
    statuses = provenance.pivot(index="event_id", columns="variable", values="value_status").add_suffix("_status")
    ordered = [c for c in FEATURE_SPEC if c in values.columns]
    wide = pd.concat([values[ordered], statuses[[c + "_status" for c in ordered]]], axis=1)
    return wide.reset_index()


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def validate_event_table(frame, name):
    """Unique event_id that equals ticker + fiscal period end; Q2 2026 only."""
    for column in ("event_id", "ticker", "fiscal_period_end"):
        if column not in frame.columns:
            raise ValueError("{} is missing column {}.".format(name, column))
        if frame[column].isna().any():
            raise ValueError("{} has missing {}.".format(name, column))
    if frame["event_id"].duplicated().any():
        raise ValueError("{} has duplicate event_id values.".format(name))
    expected = [make_event_id(t, p) for t, p in zip(frame["ticker"], frame["fiscal_period_end"])]
    if list(frame["event_id"]) != expected:
        raise ValueError("{} has event_id values that do not match ticker + fiscal_period_end.".format(name))
    if not pd.to_datetime(frame["fiscal_period_end"]).map(in_q2_2026).all():
        raise ValueError("{} has fiscal period ends outside calendar Q2 2026.".format(name))


def validate_one_to_one(left, right):
    """Joining on event_id must not add rows, and identity fields must agree."""
    merged = left[["event_id", "ticker", "fiscal_period_end"]].merge(
        right[["event_id", "ticker", "fiscal_period_end"]], on="event_id", how="inner", validate="one_to_one", suffixes=("_l", "_r")
    )
    if not (merged["ticker_l"].eq(merged["ticker_r"]).all() and merged["fiscal_period_end_l"].astype(str).eq(merged["fiscal_period_end_r"].astype(str)).all()):
        raise ValueError("Ticker or fiscal_period_end disagree across files for the same event_id.")
    return len(merged)


def write_csv(frame, path):
    """Write with blanks for missing values (never 0, NA, or -999)."""
    frame.to_csv(path, index=False, na_rep="")
