"""Offline tests for Gus's event list, CAR[0,1], and financial features.

All inputs are synthetic and built inside the tests. No network access.
"""

import io
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

import gus_event_data as g

ET = "America/New_York"
# Trading sessions around the July 3, 2026 market holiday (July 4 is a Saturday).
SESSIONS = pd.DatetimeIndex(
    ["2026-06-29", "2026-06-30", "2026-07-01", "2026-07-02", "2026-07-06", "2026-07-07",
     "2026-07-08", "2026-07-09", "2026-07-10", "2026-07-13"]
)


class IdentityTests(unittest.TestCase):
    def test_event_id_is_ticker_plus_period_end(self):
        self.assertEqual(g.make_event_id("msft", "2026-06-30"), "MSFT_2026-06-30")
        self.assertEqual(g.make_event_id("BRK.B", pd.Timestamp("2026-06-27")), "BRK.B_2026-06-27")

    def test_yahoo_symbol_uses_hyphen(self):
        self.assertEqual(g.yahoo_symbol("BRK.B"), "BRK-B")
        self.assertEqual(g.yahoo_symbol("bf.b"), "BF-B")

    def test_secondary_share_classes_map_to_class_a(self):
        self.assertEqual(g.SECONDARY_SHARE_CLASSES, {"GOOG": "GOOGL", "FOX": "FOXA", "NWS": "NWSA"})

    def test_validate_event_table_rejects_duplicates_and_bad_ids(self):
        good = pd.DataFrame({"ticker": ["AAA", "BBB"], "fiscal_period_end": ["2026-06-30", "2026-05-02"]})
        good["event_id"] = [g.make_event_id(t, p) for t, p in zip(good.ticker, good.fiscal_period_end)]
        g.validate_event_table(good, "good")
        with self.assertRaises(ValueError):
            g.validate_event_table(pd.concat([good, good.iloc[[0]]]), "dup")
        bad = good.copy()
        bad.loc[0, "event_id"] = "AAA-1"
        with self.assertRaises(ValueError):
            g.validate_event_table(bad, "bad id")
        outside = good.copy()
        outside.loc[1, "fiscal_period_end"] = "2026-03-31"
        outside["event_id"] = [g.make_event_id(t, p) for t, p in zip(outside.ticker, outside.fiscal_period_end)]
        with self.assertRaises(ValueError):
            g.validate_event_table(outside, "outside")

    def test_q2_bounds_are_inclusive(self):
        self.assertTrue(g.in_q2_2026("2026-04-01"))
        self.assertTrue(g.in_q2_2026("2026-06-30"))
        self.assertFalse(g.in_q2_2026("2026-03-31"))
        self.assertFalse(g.in_q2_2026("2026-07-01"))


class TimingTests(unittest.TestCase):
    def test_naive_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            g.assign_day0_session(pd.Timestamp("2026-07-01 07:00"), SESSIONS)

    def test_pre_market_maps_to_same_day(self):
        stamp = pd.Timestamp("2026-07-01 07:00", tz=ET)
        self.assertEqual(g.assign_day0_session(stamp, SESSIONS), pd.Timestamp("2026-07-01"))
        self.assertEqual(g.release_timing(stamp), "pre_market")

    def test_after_close_maps_to_next_session(self):
        stamp = pd.Timestamp("2026-07-01 16:05", tz=ET)
        self.assertEqual(g.assign_day0_session(stamp, SESSIONS), pd.Timestamp("2026-07-02"))
        self.assertEqual(g.release_timing(stamp), "after_close")

    def test_exactly_four_pm_is_after_close(self):
        stamp = pd.Timestamp("2026-07-01 16:00", tz=ET)
        self.assertEqual(g.assign_day0_session(stamp, SESSIONS), pd.Timestamp("2026-07-02"))

    def test_after_close_before_holiday_skips_to_next_open_session(self):
        stamp = pd.Timestamp("2026-07-02 16:30", tz=ET)
        self.assertEqual(g.assign_day0_session(stamp, SESSIONS), pd.Timestamp("2026-07-06"))

    def test_friday_after_close_maps_to_monday(self):
        stamp = pd.Timestamp("2026-07-10 16:30", tz=ET)
        self.assertEqual(g.assign_day0_session(stamp, SESSIONS), pd.Timestamp("2026-07-13"))

    def test_utc_timestamp_is_converted_to_new_york(self):
        # 20:30 UTC on July 30 is 16:30 EDT -> after close.
        stamp = pd.Timestamp("2026-07-30T20:30:28Z")
        sessions = pd.bdate_range("2026-07-29", "2026-08-04")
        self.assertEqual(g.assign_day0_session(stamp, sessions), pd.Timestamp("2026-07-31"))

    def test_weekend_maps_forward(self):
        stamp = pd.Timestamp("2026-07-04 10:00", tz=ET)
        self.assertEqual(g.assign_day0_session(stamp, SESSIONS), pd.Timestamp("2026-07-06"))

    def test_beyond_last_session_is_missing(self):
        stamp = pd.Timestamp("2026-07-13 17:00", tz=ET)
        self.assertTrue(pd.isna(g.assign_day0_session(stamp, SESSIONS)))


def _filings():
    return pd.DataFrame(
        {
            "form": ["10-Q", "8-K", "8-K", "10-Q", "8-K", "10-Q/A"],
            "reportDate": ["2026-03-28", "2026-04-30", "2026-07-30", "2026-06-27", "2026-07-15", "2026-06-27"],
            "filingDate": ["2026-05-01", "2026-04-30", "2026-07-30", "2026-07-31", "2026-07-15", "2026-08-20"],
            "acceptanceDateTime": [
                "2026-05-01T10:01:00.000Z", "2026-04-30T20:30:41.000Z", "2026-07-30T20:30:28.000Z",
                "2026-07-31T10:01:02.000Z", "2026-07-15T12:00:00.000Z", "2026-08-20T12:00:00.000Z",
            ],
            "items": ["", "2.02,9.01", "2.02,9.01", "", "5.02", ""],
        }
    )


class EdgarSelectionTests(unittest.TestCase):
    def test_selects_original_q2_periodic_filing_only(self):
        q2 = g.select_q2_periodic_filings(_filings())
        self.assertEqual(len(q2), 1)
        self.assertEqual(q2.iloc[0]["form"], "10-Q")
        self.assertEqual(q2.iloc[0]["reportDate"], pd.Timestamp("2026-06-27"))

    def test_finds_first_item_202_release_after_period_end(self):
        release = g.find_earnings_release(_filings(), "2026-06-27", "2026-07-31")
        self.assertEqual(release["acceptanceDateTime"], pd.Timestamp("2026-07-30T20:30:28Z"))

    def test_no_release_returns_none(self):
        filings = _filings()
        filings["items"] = ""
        self.assertIsNone(g.find_earnings_release(filings, "2026-06-27", "2026-07-31"))

    def test_prior_quarter_filing_is_the_preceding_quarter(self):
        prior = g.prior_quarter_filing(_filings(), "2026-06-27")
        self.assertEqual(prior["reportDate"], pd.Timestamp("2026-03-28"))
        self.assertEqual(prior["filingDate"], pd.Timestamp("2026-05-01"))


class YahooMatchTests(unittest.TestCase):
    def setUp(self):
        self.sessions = pd.bdate_range("2026-07-20", "2026-08-10")
        self.yahoo = pd.DataFrame(
            {"EPS Estimate": [1.50, 1.40], "Reported EPS": [1.60, np.nan]},
            index=pd.DatetimeIndex(["2026-07-30 16:00", "2026-10-29 16:00"]).tz_localize(ET),
        )

    def test_consistent_day0_and_eps_values(self):
        result = g.match_yahoo_event(self.yahoo, pd.Timestamp("2026-07-31"), self.sessions)
        self.assertEqual(result["timing_check"], "consistent")
        self.assertAlmostEqual(result["eps_actual"], 1.60)
        self.assertAlmostEqual(result["eps_estimate"], 1.50)

    def test_differing_day0_is_flagged(self):
        result = g.match_yahoo_event(self.yahoo, pd.Timestamp("2026-07-30"), self.sessions)
        self.assertEqual(result["timing_check"], "yahoo_day0_differs")

    def test_no_nearby_yahoo_event_is_missing_not_zero(self):
        result = g.match_yahoo_event(self.yahoo, pd.Timestamp("2026-09-15"), pd.bdate_range("2026-09-01", "2026-09-30"))
        self.assertEqual(result["timing_check"], "no_yahoo_event")
        self.assertTrue(np.isnan(result["eps_actual"]))

    def test_yahoo_fallback_picks_first_event_after_period_end(self):
        yahoo = pd.DataFrame(
            {"EPS Estimate": [1.0, 3.63, 1.40], "Reported EPS": [2.0, 3.52, np.nan]},
            index=pd.DatetimeIndex(["2026-05-01 06:00", "2026-07-31 06:00", "2026-10-30 06:00"]).tz_localize(ET),
        )
        stamp, row = g.yahoo_release_after_period(yahoo, "2026-06-30", "2026-08-11")
        self.assertEqual(stamp, pd.Timestamp("2026-07-31 06:00", tz=ET))
        self.assertAlmostEqual(row["Reported EPS"], 3.52)

    def test_yahoo_fallback_none_when_no_event_in_window(self):
        yahoo = pd.DataFrame(
            {"EPS Estimate": [1.0], "Reported EPS": [2.0]},
            index=pd.DatetimeIndex(["2026-05-01 06:00"]).tz_localize(ET),
        )
        self.assertIsNone(g.yahoo_release_after_period(yahoo, "2026-06-30", "2026-08-11"))
        self.assertIsNone(g.yahoo_release_after_period(None, "2026-06-30", "2026-08-11"))
        self.assertIsNone(g.yahoo_release_after_period(yahoo.iloc[:0], "2026-06-30", "2026-08-11"))

    def test_surprise_math_and_zero_estimate(self):
        usd, pct = g.eps_surprise(1.60, 1.50)
        self.assertAlmostEqual(usd, 0.10)
        self.assertAlmostEqual(pct, 0.10 / 1.50 * 100)
        usd, pct = g.eps_surprise(-0.20, -0.25)
        self.assertAlmostEqual(pct, 0.05 / 0.25 * 100)
        self.assertTrue(np.isnan(g.eps_surprise(0.1, 0.0)[1]))
        self.assertTrue(np.isnan(g.eps_surprise(np.nan, 1.0)[0]))


def _easy_es_results(ticker, event_date, ar0, ar1, offsets=range(-10, 11)):
    rows = []
    for offset in offsets:
        ar = {0: ar0, 1: ar1}.get(offset, 0.001)
        rows.append({"ticker": ticker, "event_date": event_date, "Offset": offset, "ar": ar, "car": np.nan, "estimation_std": 0.02, "event_id": 99})
    return pd.DataFrame(rows)


class CarTests(unittest.TestCase):
    def setUp(self):
        self.manifest = pd.DataFrame(
            {
                "event_id": ["AAA_2026-06-30", "BRK.B_2026-06-30", "CCC_2026-06-27"],
                "yahoo_symbol": ["AAA", "BRK-B", "CCC"],
                "day0_session": ["2026-07-30", "2026-08-03", "2026-07-31"],
            }
        )
        self.events = g.easy_es_input(self.manifest)

    def test_input_uses_yahoo_symbol_and_day0(self):
        self.assertEqual(list(self.events["ticker"]), ["AAA", "BRK-B", "CCC"])
        self.assertEqual(self.events.loc[1, "event_date"], "2026-08-03")

    def test_car_is_day0_plus_day1_not_package_cumulative_car(self):
        results = _easy_es_results("AAA", "2026-07-30", 0.03, -0.01)
        results["car"] = results["ar"].cumsum()  # CAR[-10, t]: must not be used
        out = g.car_0_1_from_easy_es(results, self.events).set_index("event_id")
        self.assertAlmostEqual(out.loc["AAA_2026-06-30", "car_0_1_pct"], 2.0)
        self.assertEqual(out.loc["AAA_2026-06-30", "car_0_1_status"], "complete")

    def test_package_renumbering_is_matched_on_ticker_and_date(self):
        results = pd.concat([_easy_es_results("BRK-B", "2026-08-03", 0.01, 0.01), _easy_es_results("AAA", "2026-07-30", 0.02, 0.0)])
        results["event_id"] = 0  # easy_es uses its own integers
        out = g.car_0_1_from_easy_es(results, self.events).set_index("event_id")
        self.assertAlmostEqual(out.loc["BRK.B_2026-06-30", "car_0_1_pct"], 2.0)
        self.assertAlmostEqual(out.loc["AAA_2026-06-30", "car_0_1_pct"], 2.0)

    def test_missing_day1_is_blank_with_status(self):
        results = _easy_es_results("AAA", "2026-07-30", 0.03, None, offsets=range(-10, 1))
        out = g.car_0_1_from_easy_es(results, self.events).set_index("event_id")
        self.assertTrue(np.isnan(out.loc["AAA_2026-06-30", "car_0_1_pct"]))
        self.assertEqual(out.loc["AAA_2026-06-30", "car_0_1_status"], "missing_day0_or_day1")

    def test_event_dropped_by_package_is_kept_and_blank(self):
        out = g.car_0_1_from_easy_es(_easy_es_results("AAA", "2026-07-30", 0.0, 0.0), self.events).set_index("event_id")
        self.assertEqual(out.loc["CCC_2026-06-27", "car_0_1_status"], "dropped_by_package")
        self.assertTrue(np.isnan(out.loc["CCC_2026-06-27", "car_0_1_pct"]))
        self.assertEqual(len(out), 3)

    def test_estimation_nobs_counts_calendar_expanded_window(self):
        dates = pd.bdate_range("2025-06-01", "2026-08-10")
        day0 = pd.Timestamp("2026-07-31")
        nobs = g.easy_es_estimation_nobs(dates, dates, day0)
        # 325 calendar days before day 0 hold ~232 weekdays; offsets -315..-61 keep only those beyond -60.
        expected = sum(1 for d in dates if day0 - pd.Timedelta(days=325) <= d < day0) - 60
        self.assertEqual(nobs, expected)
        self.assertLess(nobs, 255)
        self.assertTrue(np.isnan(g.easy_es_estimation_nobs(dates, dates, pd.Timestamp("2026-08-01"))))
        fewer = g.easy_es_estimation_nobs(dates, dates[dates >= "2026-01-01"], day0)
        self.assertLess(fewer, nobs)

    def test_duplicate_ticker_day0_is_rejected(self):
        dup = self.manifest.copy()
        dup.loc[2, ["yahoo_symbol", "day0_session"]] = ["AAA", "2026-07-30"]
        with self.assertRaises(ValueError):
            g.easy_es_input(dup)


def _prices(n=320, start="2025-04-01", spike_at=None):
    dates = pd.bdate_range(start, periods=n)
    rng = np.random.default_rng(0)
    market = 100 * np.cumprod(1 + rng.normal(0.0004, 0.01, n))
    stock = 50 * np.cumprod(1 + 1.5 * (market / np.r_[market[0], market[:-1]] - 1) + rng.normal(0, 0.005, n))
    frame = pd.DataFrame({"Adj Close": stock, "Close": stock * 1.02, "Volume": np.full(n, 1_000_000.0)}, index=dates)
    if spike_at is not None:
        frame.loc[frame.index >= spike_at, ["Adj Close", "Close"]] *= 5
        frame.loc[frame.index >= spike_at, "Volume"] *= 50
    return frame, pd.Series(market, index=dates)


class PointInTimeTests(unittest.TestCase):
    def setUp(self):
        self.prices, self.market = _prices()
        self.day0 = self.prices.index[300]

    def _values(self, rows):
        return {r["variable"]: r["value"] for r in rows}

    def test_day0_and_later_prices_do_not_change_features(self):
        base_rows, base_close, _ = g.price_features(self.prices, self.market, self.day0)
        spiked, market = _prices(spike_at=self.day0)
        spike_rows, spike_close, _ = g.price_features(spiked, market, self.day0)
        self.assertEqual(self._values(base_rows), self._values(spike_rows))
        self.assertEqual(base_close, spike_close)

    def test_beta_is_recovered_and_known_by_is_before_day0(self):
        rows, _, close_date = g.price_features(self.prices, self.market, self.day0)
        values = self._values(rows)
        self.assertAlmostEqual(values["beta_252d"], 1.5, delta=0.15)
        self.assertLess(close_date, self.day0)
        for row in rows:
            self.assertLess(row["known_by_date"], self.day0)

    def test_short_history_is_missing_not_zero(self):
        rows, _, _ = g.price_features(self.prices.iloc[:120], self.market.iloc[:120], self.prices.index[119])
        statuses = {r["variable"]: r["value_status"] for r in rows}
        values = self._values(rows)
        self.assertEqual(statuses["return_52w_pct"], g.STATUS_UNAVAILABLE)
        self.assertTrue(np.isnan(values["return_52w_pct"]))
        self.assertTrue(np.isnan(values["beta_252d"]))

    def test_latest_shares_ignore_values_dated_on_or_after_day0(self):
        shares = pd.Series([100.0, 110.0, 999.0], index=pd.to_datetime(["2026-04-01", "2026-07-01", "2026-07-30"]))
        value, date = g.latest_before(shares, pd.Timestamp("2026-07-30"))
        self.assertEqual(value, 110.0)
        self.assertEqual(date, pd.Timestamp("2026-07-01"))

    def test_unadjusted_close_undoes_only_later_splits(self):
        splits = pd.Series([2.0, 10.0], index=pd.to_datetime(["2026-01-05", "2026-09-01"]))
        self.assertAlmostEqual(g.unadjusted_close(20.0, pd.Timestamp("2026-07-29"), splits), 200.0)
        self.assertAlmostEqual(g.unadjusted_close(20.0, pd.Timestamp("2026-07-29"), pd.Series(dtype=float)), 20.0)


def _statements():
    periods = pd.to_datetime(["2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30", "2025-06-30"])
    income = pd.DataFrame(
        [[130.0, 100.0, 90.0, 85.0, 80.0], [13.0, 10.0, 9.0, 8.0, 7.0]],
        index=["Total Revenue", "Net Income"], columns=periods,
    )
    balance = pd.DataFrame(
        [[500.0, 400.0, 390.0, 380.0, 370.0], [250.0, 200.0, 195.0, 190.0, 185.0]],
        index=["Stockholders Equity", "Total Debt"], columns=periods,
    )
    return income, balance


class StatementTests(unittest.TestCase):
    def test_uses_prior_quarter_not_event_quarter(self):
        income, balance = _statements()
        rows = g.statement_features(income, balance, "2026-03-31", "2026-05-01", pd.Timestamp("2026-07-30"), 2000.0)
        values = {r["variable"]: r["value"] for r in rows}
        self.assertAlmostEqual(values["price_to_book"], 2000.0 / 400.0)
        self.assertAlmostEqual(values["profit_margin_pct"], 10.0)
        self.assertAlmostEqual(values["debt_to_equity"], 0.5)
        for row in rows:
            self.assertEqual(row["source_period_end"], pd.Timestamp("2026-03-31"))
            self.assertLess(row["known_by_date"], pd.Timestamp("2026-07-30"))

    def test_year_ago_quarter_missing_is_unavailable(self):
        income, balance = _statements()
        rows = g.statement_features(income, balance, "2026-03-31", "2026-05-01", pd.Timestamp("2026-07-30"), 2000.0)
        status = {r["variable"]: r["value_status"] for r in rows}
        self.assertEqual(status["revenue_growth_yoy_pct"], g.STATUS_UNAVAILABLE)
        self.assertEqual(status["earnings_growth_yoy_pct"], g.STATUS_UNAVAILABLE)

    def test_year_ago_growth_when_available(self):
        income, balance = _statements()
        rows = g.statement_features(income, balance, "2026-06-30", "2026-07-25", pd.Timestamp("2026-10-30"), 2000.0)
        values = {r["variable"]: r["value"] for r in rows}
        self.assertAlmostEqual(values["revenue_growth_yoy_pct"], (130 / 80 - 1) * 100)
        self.assertAlmostEqual(values["earnings_growth_yoy_pct"], (13 / 7 - 1) * 100)

    def test_filing_on_or_after_day0_is_not_point_in_time(self):
        income, balance = _statements()
        rows = g.statement_features(income, balance, "2026-03-31", "2026-07-30", pd.Timestamp("2026-07-30"), 2000.0)
        for row in rows:
            self.assertEqual(row["value_status"], g.STATUS_NOT_PIT)
            self.assertTrue(np.isnan(row["value"]))

    def test_negative_equity_leaves_ratios_missing(self):
        income, balance = _statements()
        balance.loc["Stockholders Equity"] = -10.0
        rows = g.statement_features(income, balance, "2026-03-31", "2026-05-01", pd.Timestamp("2026-07-30"), 2000.0)
        values = {r["variable"]: r["value"] for r in rows}
        self.assertTrue(np.isnan(values["price_to_book"]))
        self.assertTrue(np.isnan(values["debt_to_equity"]))

    def test_unverified_consensus_status_keeps_value(self):
        row = g._value("eps_surprise_usd", 0.1, g.STATUS_OBSERVED_CONSENSUS_NOT_PIT, "x")
        self.assertEqual(row["value_status"], "observed_consensus_not_pit")
        self.assertAlmostEqual(row["value"], 0.1)
        self.assertNotEqual(row["value_status"], g.STATUS_OBSERVED)
        blank = g._value("eps_surprise_usd", np.nan, g.STATUS_OBSERVED_CONSENSUS_NOT_PIT, "x")
        self.assertEqual(blank["value_status"], g.STATUS_UNAVAILABLE)
        self.assertIn(g.STATUS_OBSERVED_CONSENSUS_NOT_PIT, g.VALUE_STATUSES)

    def test_current_only_fields_are_always_blank(self):
        for row in g.current_only_rows():
            self.assertEqual(row["value_status"], g.STATUS_CURRENT_ONLY)
            self.assertTrue(np.isnan(row["value"]))


class OutputTests(unittest.TestCase):
    def _tables(self):
        events = pd.DataFrame({"ticker": ["AAA", "BBB"], "fiscal_period_end": ["2026-06-30", "2026-05-02"]})
        events["event_id"] = [g.make_event_id(t, p) for t, p in zip(events.ticker, events.fiscal_period_end)]
        return events, events.copy()

    def test_one_to_one_join_does_not_multiply_rows(self):
        left, right = self._tables()
        self.assertEqual(g.validate_one_to_one(left, right), 2)
        with self.assertRaises(Exception):
            g.validate_one_to_one(left, pd.concat([right, right.iloc[[0]]]))

    def test_join_rejects_disagreeing_identity(self):
        left, right = self._tables()
        right.loc[0, "fiscal_period_end"] = "2026-06-27"
        with self.assertRaises(ValueError):
            g.validate_one_to_one(left, right)

    def test_missing_values_round_trip_as_blank(self):
        frame = pd.DataFrame({"event_id": ["A_2026-06-30"], "car_0_1_pct": [np.nan], "beta_252d": [0.0]})
        buffer = io.StringIO()
        frame.to_csv(buffer, index=False, na_rep="")
        text = buffer.getvalue()
        self.assertIn("A_2026-06-30,,0.0", text)
        back = pd.read_csv(io.StringIO(text))
        self.assertTrue(np.isnan(back.loc[0, "car_0_1_pct"]))
        self.assertEqual(back.loc[0, "beta_252d"], 0.0)

    def test_wide_features_keeps_value_and_status(self):
        rows = []
        for event in ["A_2026-06-30", "B_2026-06-30"]:
            for row in g.current_only_rows() + [g._value("beta_252d", 1.1, g.STATUS_OBSERVED, "x")]:
                rows.append(dict(row, event_id=event))
        wide = g.wide_features(pd.DataFrame(rows))
        self.assertEqual(len(wide), 2)
        self.assertIn("forward_pe_status", wide.columns)
        self.assertTrue(wide["forward_pe"].isna().all())
        self.assertTrue((wide["beta_252d"] == 1.1).all())


if __name__ == "__main__":
    unittest.main()
