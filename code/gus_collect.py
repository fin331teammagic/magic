"""Collect Gus's checkpoint data: event list, CAR[0,1], and Yahoo features.

Run from the repository root:

    export SEC_USER_AGENT="Your Name your.email@example.edu"   # required by SEC
    python code/gus_collect.py manifest
    python code/gus_collect.py event-study
    python code/gus_collect.py features

Sources (approved by the team for this checkpoint):
- SEC EDGAR submissions API: fiscal period ends (10-Q/10-K report dates),
  earnings-release timestamps (8-K Item 2.02 acceptance time), and the
  filing date of the prior quarter's report. SEC fair-access rules require a
  declared User-Agent with contact details and at most 10 requests/second.
- Yahoo Finance via yfinance: EPS actual and consensus, prices, shares,
  quarterly statements. Yahoo's consensus is not a preserved point-in-time
  record; this is flagged in `earnings_source`.
- easy_es 0.1.8 (the Lecture 13 package) with Kenneth French daily factors.

Raw downloads are cached under data/raw/ (git-ignored); only derived,
documented outputs are written to inputs/ and outputs/.
"""

import argparse
import io
import json
import os
import pickle
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gus_event_data as g  # noqa: E402

ROSTER = Path("inputs/sp500_constituents_20260630.csv")
MANIFEST = Path("inputs/q2_2026_events.csv")
EXCLUSIONS = Path("outputs/q2_2026_exclusions.csv")
EVENT_STUDY = Path("outputs/q2_2026_event_study.csv")
FEATURES = Path("outputs/q2_2026_financial_features.csv")
PROVENANCE = Path("outputs/q2_2026_feature_provenance.csv")
RAW = Path("data/raw")

FRENCH_FF5_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
ES_SETTINGS = dict(estimation_days=255, gap_days=50, window_before=10, window_after=10, min_estimation_days=100, estimator_type="ff5")
YAHOO_SOURCE = "Yahoo Finance via yfinance {}"
EPS_SOURCE = "Yahoo Finance get_earnings_dates (Reported EPS, EPS Estimate); consensus not point-in-time verified"
TIMESTAMP_BASIS = "SEC 8-K Item 2.02 acceptance time (filing time; press release may precede it by minutes)"


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def _cache(path, fetch):
    path = RAW / path
    if path.exists():
        try:
            with open(path, "rb") as handle:
                return pickle.load(handle)
        except Exception as error:  # e.g. cache written by another pandas version
            print("  cache unreadable, re-downloading {} ({})".format(path.name, str(error)[:60]))
    value = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        pickle.dump(value, handle)
    return value


def _retry(fetch, attempts=4, wait=3.0):
    for attempt in range(attempts):
        try:
            return fetch()
        except Exception as error:  # network/source errors are retried, then raised
            if attempt == attempts - 1:
                raise
            print("  retry after error: {}".format(str(error)[:120]))
            time.sleep(wait * (attempt + 1))


def _sec_get(url):
    import urllib.request

    agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if not agent:
        raise SystemExit("Set SEC_USER_AGENT to 'Name contact-email' before querying EDGAR.")
    request = urllib.request.Request(url, headers={"User-Agent": agent, "Accept-Encoding": "identity"})
    time.sleep(0.15)  # stay well under SEC's 10 requests/second
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def edgar_filings(cik):
    cik10 = "{:010d}".format(int(cik))

    def fetch():
        data = json.loads(_sec_get("https://data.sec.gov/submissions/CIK{}.json".format(cik10)))
        return pd.DataFrame(data["filings"]["recent"])

    return _cache("edgar/{}.pkl".format(cik10), lambda: _retry(fetch))


def filing_url(cik, accession):
    return "https://www.sec.gov/Archives/edgar/data/{}/{}/{}-index.htm".format(int(cik), accession.replace("-", ""), accession)


def yahoo_history(symbol, start, end):
    import yfinance as yf

    key = "yahoo/history/{}_{}_{}.pkl".format(symbol, start, end)
    return _cache(key, lambda: _retry(lambda: yf.Ticker(symbol).history(start=start, end=end, auto_adjust=False, actions=True)))


def trading_sessions(as_of):
    spy = yahoo_history("SPY", "2024-06-01", as_of)
    index = pd.DatetimeIndex(spy.index)
    if index.tz is not None:
        index = index.tz_convert(g.EASTERN).tz_localize(None)
    return index.normalize().unique().sort_values()


def _iso(value):
    return "" if pd.isna(value) else pd.Timestamp(value).isoformat()


def _date(value):
    return "" if pd.isna(value) else pd.Timestamp(value).strftime("%Y-%m-%d")


# --------------------------------------------------------------------------
# Step 1: verified event list
# --------------------------------------------------------------------------

def build_manifest(as_of, tickers=None):
    import yfinance as yf

    roster = pd.read_csv(ROSTER)
    if tickers:
        roster = roster[roster["Symbol"].isin(tickers)]
    sessions = trading_sessions(as_of)
    retrieved = pd.Timestamp.now(tz="UTC").isoformat()
    rows, exclusions = [], []

    for number, company in enumerate(roster.itertuples(index=False), start=1):
        ticker = str(company.Symbol).strip().upper()
        if number % 25 == 0:
            print("manifest: {}/{} {}".format(number, len(roster), ticker))
        if ticker in g.SECONDARY_SHARE_CLASSES:
            exclusions.append((ticker, "secondary_share_class", "same call as {}".format(g.SECONDARY_SHARE_CLASSES[ticker])))
            continue
        try:
            filings = edgar_filings(company.CIK)
        except Exception as error:
            exclusions.append((ticker, "edgar_unavailable", str(error)[:200]))
            continue

        try:
            periodic = g.select_q2_periodic_filings(filings)
            if periodic.empty:
                exclusions.append((ticker, "no_q2_2026_periodic_filing", "no 10-Q/10-K with period end 2026-04-01..2026-06-30"))
                continue
            if periodic["reportDate"].nunique() > 1:
                exclusions.append((ticker, "multiple_q2_2026_periods", ";".join(periodic["reportDate"].dt.strftime("%Y-%m-%d"))))
                continue
            report = periodic.sort_values("filingDate").iloc[0]
            period_end = report["reportDate"]

            release = g.find_earnings_release(filings, period_end, report["filingDate"])
            if release is None:
                exclusions.append((ticker, "no_item_202_8k", "no 8-K Item 2.02 between period end and periodic filing"))
                continue
            stamp = release["acceptanceDateTime"].tz_convert(g.EASTERN)
            day0 = g.assign_day0_session(stamp, sessions)
            prior = g.prior_quarter_filing(filings, period_end)

            symbol = g.yahoo_symbol(ticker)
            try:
                yahoo = _cache("yahoo/earnings/{}.pkl".format(symbol), lambda: _retry(lambda: yf.Ticker(symbol).get_earnings_dates(limit=16)))
            except Exception as error:
                yahoo = None
                print("  {}: Yahoo earnings dates unavailable ({})".format(ticker, str(error)[:80]))
            match = g.match_yahoo_event(yahoo, day0, sessions)
            surprise_usd, surprise_pct = g.eps_surprise(match["eps_actual"], match["eps_estimate"])

            rows.append(
                {
                    "event_id": g.make_event_id(ticker, period_end),
                    "ticker": ticker,
                    "yahoo_symbol": symbol,
                    "cik": int(company.CIK),
                    "company": company.Security,
                    "gics_sector": company._2 if hasattr(company, "_2") else getattr(company, "GICS Sector", ""),
                    "fiscal_period_end": _date(period_end),
                    "fiscal_period_form": report["form"],
                    "fiscal_period_end_source": filing_url(company.CIK, report["accessionNumber"]),
                    "periodic_filing_date": _date(report["filingDate"]),
                    "earnings_timestamp": _iso(stamp),
                    "release_timing": g.release_timing(stamp),
                    "timestamp_basis": TIMESTAMP_BASIS,
                    "event_timestamp_source": filing_url(company.CIK, release["accessionNumber"]),
                    "day0_session": _date(day0),
                    "yahoo_earnings_timestamp": _iso(match["yahoo_timestamp"]),
                    "yahoo_day0_session": _date(match["yahoo_day0_session"]),
                    "timing_check": match["timing_check"],
                    "primary_timing_sample": match["timing_check"] == "consistent",
                    "eps_actual": match["eps_actual"],
                    "eps_estimate": match["eps_estimate"],
                    "eps_surprise_usd": surprise_usd,
                    "eps_surprise_pct": surprise_pct,
                    "earnings_source": EPS_SOURCE if pd.notna(match["eps_actual"]) or pd.notna(match["eps_estimate"]) else "",
                    "prior_period_end": _date(prior["reportDate"]) if prior is not None else "",
                    "prior_filing_date": _date(prior["filingDate"]) if prior is not None else "",
                    "prior_filing_source": filing_url(company.CIK, prior["accessionNumber"]) if prior is not None else "",
                    "retrieved_at_utc": retrieved,
                    "data_status": "cohort",
                }
            )
        except Exception as error:  # keep going; record why this company is missing
            exclusions.append((ticker, "processing_error", str(error)[:200]))
            continue
        time.sleep(0.2)

    manifest = pd.DataFrame(rows).sort_values("event_id").reset_index(drop=True)
    g.validate_event_table(manifest, "event manifest")
    if manifest["ticker"].duplicated().any() or manifest["cik"].duplicated().any():
        raise ValueError("More than one event per ticker or CIK.")
    g.write_csv(manifest, MANIFEST)
    excluded = pd.DataFrame(exclusions, columns=["ticker", "reason", "detail"])
    EXCLUSIONS.parent.mkdir(exist_ok=True)
    g.write_csv(excluded, EXCLUSIONS)
    print("events: {} | excluded: {} | timing checks: {}".format(len(manifest), len(excluded), manifest["timing_check"].value_counts().to_dict()))


# --------------------------------------------------------------------------
# Step 2: CAR[0,1] with easy_es
# --------------------------------------------------------------------------

def french_ff5():
    """Daily FF5 factors as fractions, plus the CRSP vintage line."""
    raw = _cache("french/ff5_daily.pkl", lambda: _retry(lambda: _download(FRENCH_FF5_URL)))
    archive = zipfile.ZipFile(io.BytesIO(raw))
    text = archive.read(archive.namelist()[0]).decode("latin-1")
    vintage = text.splitlines()[0].strip()
    frame = pd.read_csv(io.StringIO(text), skiprows=3)
    frame = frame.rename(columns={frame.columns[0]: "Date"})
    frame["Date"] = pd.to_datetime(frame["Date"].astype(str).str.strip(), format="%Y%m%d", errors="coerce").dt.date
    frame = frame.dropna()
    factors = [c for c in frame.columns if c != "Date"]
    frame[factors] = frame[factors].astype(float) / 100  # easy_es only rescales when it downloads itself
    return frame, vintage


def _download(url):
    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": "TeamMagic-FIN331-research"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def easy_es_returns(symbols, as_of):
    """Daily returns in easy_es's format, built exactly as its loader does
    (Adj Close percent change, NaNs dropped), from the cached Yahoo histories
    shared with the features step."""
    frames = []
    for symbol in symbols:
        try:
            history = yahoo_history(symbol, "2024-06-01", as_of)
        except Exception as error:
            print("  {}: no Yahoo prices ({})".format(symbol, str(error)[:80]))
            continue
        if history is None or history.empty or "Adj Close" not in history:
            continue
        frame = pd.DataFrame({"Ret": history["Adj Close"].pct_change(fill_method=None), "Volume": history["Volume"]})
        index = pd.DatetimeIndex(history.index)
        frame.index = index.tz_convert(g.EASTERN).tz_localize(None) if index.tz is not None else index
        frame = frame.dropna().reset_index(names="Date")
        frame["Date"] = frame["Date"].dt.date
        frame["ticker"] = symbol
        frames.append(frame[["ticker", "Date", "Ret", "Volume"]])
    return pd.concat(frames, ignore_index=True)


def run_event_study(as_of):
    from easy_es import EventStudy
    import easy_es

    manifest = pd.read_csv(MANIFEST, dtype={"cik": str})
    events = g.easy_es_input(manifest)
    factors, vintage = french_ff5()
    last_factor = max(factors["Date"])
    print("French factors: {} | last date {}".format(vintage, last_factor))

    study = EventStudy(n_cores=1, **ES_SETTINGS)
    study.add_factors(factors_df=factors)
    study.add_returns(ret_df=easy_es_returns(events["ticker"].unique(), as_of))
    results = study.run_study(events[["ticker", "event_date"]])

    car = g.car_0_1_from_easy_es(results, events)
    returns = study.returns_df
    factor_dates = list(factors["Date"])
    settings = {k: ES_SETTINGS[k] for k in ("estimation_days", "gap_days", "window_before", "window_after")}
    car["estimation_nobs"] = [
        g.easy_es_estimation_nobs(returns.loc[returns["ticker"] == t, "Date"], factor_dates, d, **settings)
        for t, d in zip(events["ticker"], events["event_date"])
    ]
    car.loc[pd.to_datetime(events["event_date"]).dt.date.to_numpy() >= last_factor, "car_0_1_status"] = "factor_data_ends_before_day1"

    keep = ["event_id", "ticker", "fiscal_period_end", "earnings_timestamp", "day0_session", "timing_check", "primary_timing_sample"]
    out = manifest[keep].merge(car, on="event_id", how="left", validate="one_to_one")
    out["car_0_1_status"] = out["car_0_1_status"].fillna("not_run_no_day0")
    out["car_model"] = "easy_es {} {}; estimation_days={} gap_days={} window=[-{},+{}] min_estimation_days={}".format(
        getattr(easy_es, "__version__", "0.1.8"), ES_SETTINGS["estimator_type"], ES_SETTINGS["estimation_days"],
        ES_SETTINGS["gap_days"], ES_SETTINGS["window_before"], ES_SETTINGS["window_after"], ES_SETTINGS["min_estimation_days"])
    out["factor_source"] = "Kenneth French Data Library, Fama/French 5 Factors (2x3) daily; " + vintage
    out["prices_source"] = "Yahoo Finance Adj Close via yfinance (returns built as easy_es does)"
    out["retrieved_at_utc"] = pd.Timestamp.now(tz="UTC").isoformat()
    out["data_status"] = "cohort"
    g.validate_event_table(out, "event study")
    g.validate_one_to_one(manifest, out)
    g.write_csv(out, EVENT_STUDY)
    print("CAR[0,1] status: {}".format(out["car_0_1_status"].value_counts().to_dict()))


# --------------------------------------------------------------------------
# Step 3: Yahoo financial features as of day -1
# --------------------------------------------------------------------------

def build_features(as_of):
    import yfinance as yf

    manifest = pd.read_csv(MANIFEST, dtype={"cik": str})
    spy = yahoo_history("SPY", "2024-06-01", as_of)["Adj Close"]
    source = YAHOO_SOURCE.format(yf.__version__)
    retrieved = pd.Timestamp.now(tz="UTC").isoformat()
    records = []

    for number, event in enumerate(manifest.itertuples(index=False), start=1):
        if number % 25 == 0:
            print("features: {}/{} {}".format(number, len(manifest), event.ticker))
        rows = []
        day0 = pd.Timestamp(event.day0_session) if isinstance(event.day0_session, str) and event.day0_session else pd.NaT
        usd, pct = event.eps_surprise_usd, event.eps_surprise_pct
        eps_status = g.STATUS_OBSERVED if pd.notna(usd) else g.STATUS_UNAVAILABLE
        rows.append(g._value("eps_surprise_usd", usd, eps_status, "Reported EPS - EPS Estimate", note="consensus not point-in-time verified"))
        rows.append(g._value("eps_surprise_pct", pct, g.STATUS_OBSERVED if pd.notna(pct) else g.STATUS_UNAVAILABLE, "Reported EPS, EPS Estimate"))
        rows.extend(g.current_only_rows())

        if pd.isna(day0):
            for name in ("log_market_cap", "price_to_book", "profit_margin_pct", "revenue_growth_yoy_pct", "earnings_growth_yoy_pct",
                         "debt_to_equity", "beta_252d", "return_52w_pct", "ma50_ma200_gap_pct", "avg_daily_volume_63d"):
                rows.append(g._value(name, None, g.STATUS_UNAVAILABLE, "", note="no day-0 session"))
        else:
            symbol = event.yahoo_symbol
            try:
                prices = yahoo_history(symbol, "2024-06-01", as_of)
                ticker = yf.Ticker(symbol)
                shares = _cache("yahoo/shares/{}.pkl".format(symbol), lambda: _retry(lambda: ticker.get_shares_full(start="2025-06-01", end=as_of)))
                income = _cache("yahoo/income_q/{}.pkl".format(symbol), lambda: _retry(lambda: ticker.quarterly_income_stmt))
                balance = _cache("yahoo/balance_q/{}.pkl".format(symbol), lambda: _retry(lambda: ticker.quarterly_balance_sheet))
            except Exception as error:
                prices = None
                note = "Yahoo download failed: {}".format(str(error)[:80])
            if prices is None or prices.empty:
                for name in ("log_market_cap", "price_to_book", "profit_margin_pct", "revenue_growth_yoy_pct", "earnings_growth_yoy_pct",
                             "debt_to_equity", "beta_252d", "return_52w_pct", "ma50_ma200_gap_pct", "avg_daily_volume_63d"):
                    rows.append(g._value(name, None, g.STATUS_UNAVAILABLE, "", note=locals().get("note", "no Yahoo prices")))
            else:
                try:
                    price_rows, close, close_date = g.price_features(prices, spy, day0)
                    rows.extend(price_rows)
                    splits = g.pre_event_window(prices["Stock Splits"], pd.Timestamp("2100-01-01")) if "Stock Splits" in prices else pd.Series(dtype=float)
                    later_splits = splits[(splits > 0) & (splits.index > close_date)] if pd.notna(close_date) else splits[splits > 0]
                    share_count, share_date = g.latest_before(shares, day0) if shares is not None and len(shares) else (np.nan, pd.NaT)
                    market_cap = np.nan
                    if len(later_splits):
                        rows.append(g._value("log_market_cap", None, g.STATUS_UNAVAILABLE, "Close x shares", note="split after day -1; share-count basis unverified"))
                    elif pd.notna(close) and pd.notna(share_count) and share_count > 0:
                        market_cap = close * share_count
                        rows.append(g._value("log_market_cap", float(np.log(market_cap)), g.STATUS_OBSERVED, "Close x get_shares_full",
                                             max(close_date, share_date), note="shares dated {}".format(_date(share_date))))
                    else:
                        rows.append(g._value("log_market_cap", None, g.STATUS_UNAVAILABLE, "Close x get_shares_full", note="no share count dated within 200 days before day 0"))
                    rows.extend(g.statement_features(income, balance, event.prior_period_end or pd.NaT, event.prior_filing_date or pd.NaT, day0, market_cap))
                except Exception as error:  # record and continue
                    done = {r["variable"] for r in rows}
                    for name in ("log_market_cap", "price_to_book", "profit_margin_pct", "revenue_growth_yoy_pct", "earnings_growth_yoy_pct",
                                 "debt_to_equity", "beta_252d", "return_52w_pct", "ma50_ma200_gap_pct", "avg_daily_volume_63d"):
                        if name not in done:
                            rows.append(g._value(name, None, g.STATUS_UNAVAILABLE, "", note="processing error: {}".format(str(error)[:80])))
        for row in rows:
            row.update(event_id=event.event_id, source=source, retrieved_at_utc=retrieved)
            records.append(row)
        time.sleep(0.1)

    provenance = pd.DataFrame(records)
    provenance["known_by_date"] = provenance["known_by_date"].map(_date)
    provenance["source_period_end"] = provenance["source_period_end"].map(_date)
    bad = provenance[(provenance["value_status"] == g.STATUS_OBSERVED) & provenance["value"].isna()]
    if len(bad):
        raise ValueError("Observed status with blank value: {}".format(bad[["event_id", "variable"]].head()))
    check = provenance.merge(manifest[["event_id", "day0_session"]], on="event_id")
    late = check[(check["known_by_date"] != "") & (check["known_by_date"] >= check["day0_session"])]
    if len(late):
        raise ValueError("Features dated on or after day 0: {}".format(late[["event_id", "variable"]].head()))

    wide = g.wide_features(provenance)
    wide = manifest[["event_id", "ticker", "fiscal_period_end", "day0_session", "gics_sector"]].merge(wide, on="event_id", how="left", validate="one_to_one")
    wide["as_of_rule"] = "information dated before day0_session (day -1); fundamentals from the prior fiscal quarter"
    wide["source"] = source
    wide["retrieved_at_utc"] = retrieved
    wide["data_status"] = "cohort"
    g.validate_event_table(wide, "financial features")
    g.validate_one_to_one(manifest, wide)
    g.write_csv(wide, FEATURES)
    g.write_csv(provenance[["event_id", "variable", "value", "value_status", "source_field", "source_period_end", "known_by_date", "note", "source", "retrieved_at_utc"]], PROVENANCE)
    print(provenance.groupby(["variable", "value_status"]).size().unstack(fill_value=0).to_string())


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=["manifest", "event-study", "features"])
    parser.add_argument("--as-of", default="2026-11-13", help="last date of price data to request (YYYY-MM-DD)")
    parser.add_argument("--tickers", nargs="*", help="manifest only: limit to these roster symbols (for testing)")
    args = parser.parse_args()
    if args.step == "manifest":
        build_manifest(args.as_of, args.tickers)
    elif args.step == "event-study":
        run_event_study(args.as_of)
    else:
        build_features(args.as_of)


if __name__ == "__main__":
    main()
