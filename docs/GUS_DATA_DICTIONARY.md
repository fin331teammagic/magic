# Gus's checkpoint datasets: event list, CAR[0,1], and Yahoo features

Status: checkpoint handoff for Cammy (analysis), Abby (transcript features), and
Michelle (dashboard). Built by `code/gus_collect.py` from the pure, tested
logic in `code/gus_event_data.py` (`tests/test_gus_event_data.py`).

## Files

| File | One row per | Purpose |
|---|---|---|
| `inputs/q2_2026_events.csv` | company-quarter event | Verified event list: identity, fiscal period end, release timestamp, day 0, EPS, sources |
| `outputs/q2_2026_exclusions.csv` | roster stock without an event | Reason each roster stock is not in the event list |
| `outputs/q2_2026_event_study.csv` | event | Checkpoint outcome `car_0_1_pct` from easy_es |
| `outputs/q2_2026_financial_features.csv` | event | Cammy's Run 1 variables, each with a `<name>_status` column |
| `outputs/q2_2026_feature_provenance.csv` | event × variable | Source field, source period, date known, and notes for every value |

## Shared conventions

- **Join key:** `event_id` = `{ticker}_{fiscal_period_end}`, e.g. `MSFT_2026-06-30`
  or `BRK.B_2026-06-27`. `ticker` matches `Symbol` in the June 30, 2026 roster;
  `fiscal_period_end` is `YYYY-MM-DD`. Every file is validated for unique
  `event_id`, agreement with ticker + period end, and 1:1 joins.
- **Missing values** are blank cells, never `0`. The reason is in a status
  column (`car_0_1_status`, `<feature>_status`) or `note`.
- **Units:** returns, surprises, margins, and growth in percent (`6.88` = 6.88%);
  EPS in USD per share; ratios unitless; volume in shares.
- **`data_status`** is `cohort` on every row (real data, target cohort).

## Sample construction

1. Start from the 503-stock roster (`inputs/sp500_constituents_20260630.csv`).
2. Drop secondary share classes that share one earnings call: GOOG (keep
   GOOGL), FOX (keep FOXA), NWS (keep NWSA). Logged as `secondary_share_class`.
3. **Fiscal period end:** the company's original 10-Q or 10-K whose SEC
   `reportDate` falls April 1 to June 30, 2026 (EDGAR submissions API).
   Stocks with none, or more than one, are excluded with a reason.
4. **Release timestamp:** acceptance time of the first 8-K with Item 2.02
   (Results of Operations) filed after the period end and no later than 7 days
   after the 10-Q/10-K. Stored in New York time with its UTC offset. This is the
   SEC filing time; the press release can precede it by minutes. The market
   reacts to the release; the call usually follows on the same day (or the
   next morning for after-close releases), so it maps to the same day 0.
   **Fallback:** if a company has no Item 2.02 8-K (e.g. it furnished results
   under another item), the first Yahoo earnings event after the period end
   (and within 7 days of the 10-Q/10-K) is used instead, with
   `timing_check = yahoo_only_no_sec_8k` and `primary_timing_sample = False`.
   Companies with neither are excluded as `no_item_202_8k_or_yahoo_event`.
5. **Day 0** follows the repository rule in `code/pead_pipeline.py`: at or
   after 16:00 New York time maps to the next trading session; earlier times
   map to the first session on or after that date (weekends/holidays roll
   forward). Sessions come from SPY's Yahoo trading calendar.
6. **Second-source timing check:** Yahoo's earnings timestamp is mapped to a
   day 0 with the same rule. `timing_check` is `consistent`,
   `yahoo_day0_differs`, `no_yahoo_event`, or `yahoo_only_no_sec_8k`.
   `primary_timing_sample` is true only when SEC and Yahoo agree.
   **Use `primary_timing_sample == True` for the main analysis; use all events
   only as a robustness check.**
7. **EPS:** Yahoo `Reported EPS` and `EPS Estimate` for the matched Yahoo event.
   Yahoo's consensus is not a preserved point-in-time record; this is stated
   in `earnings_source`. Missing EPS stays blank.

## `outputs/q2_2026_event_study.csv` (checkpoint Y)

- Package: **easy_es 0.1.8** (Lecture 13 companion notebook), `estimator_type="ff5"`,
  `estimation_days=255`, `gap_days=50`, window −10 to +10, `min_estimation_days=100`.
- Factors: Kenneth French daily Fama/French 5 Factors (2x3), passed in as
  fractions; the file's CRSP vintage line is recorded in `factor_source`.
  The vintage used ends September 30, 2026, after every event's day 1.
- Prices: Yahoo `Adj Close` daily returns, built exactly as easy_es's loader
  does, from the same cached histories as the features.
- **`car_0_1_pct` = AR(day 0) + AR(day 1)**, in percent. easy_es's own `car`
  column cumulates from day −10 and is **not** used. Components are in
  `ar_day0_pct` and `ar_day1_pct`.
- `estimation_nobs` is the number of estimation-window days easy_es actually
  used. easy_es expands events by calendar days, so this is about 164 trading
  days, not 255.
- `car_0_1_status`: `complete`, `missing_day0_or_day1`, `dropped_by_package`
  (e.g. fewer than 100 estimation days or no Yahoo prices), or
  `factor_data_ends_before_day1`.
- This checkpoint outcome is distinct from the project's final outcome
  (20-session ETF-proxy abnormal return after the reaction session, in
  `code/pead_pipeline.py`). Neither is a SPY buy-and-hold abnormal return,
  and the ETF proxies are not Kenneth French factors.

## `outputs/q2_2026_financial_features.csv` (Run 1 X)

Status values: `observed` (verified value), `observed_consensus_not_pit`
(value present but rests on Yahoo's unverified consensus; EPS surprise only),
`missing_unavailable`, `missing_not_point_in_time`, `excluded_current_only`.
A historical point-in-time consensus would need another source such as
I/B/E/S via WRDS; the checkpoint uses Yahoo only, per the course restriction.

All values use information dated strictly before day 0. Fundamentals come
from the **prior fiscal quarter**, whose 10-Q/10-K filing date (from EDGAR) must
precede day 0; the event quarter's own figures are released at the call and
are never used.

| Variable | Unit | Measurement | Point-in-time status |
|---|---|---|---|
| `eps_surprise_usd` | USD/share | actual − consensus | Status `observed_consensus_not_pit`: Yahoo consensus is not point-in-time verified; treat as unverified |
| `eps_surprise_pct` | % | (actual − consensus) / \|consensus\| × 100; blank if consensus = 0 | Same |
| `log_market_cap` | ln(USD) | unadjusted close on day −1 × latest Yahoo share count dated before day 0 | Rebuilt; blank if a split occurred after day −1 |
| `price_to_book` | ratio | market cap / prior-quarter stockholders' equity | Rebuilt; blank if equity ≤ 0 |
| `profit_margin_pct` | % | prior-quarter net income / revenue | Rebuilt (quarterly, not Yahoo's trailing-12-month snapshot) |
| `revenue_growth_yoy_pct` | % | prior quarter vs same quarter a year earlier | Mostly blank: Yahoo's quarterly history does not reach the year-ago quarter |
| `earnings_growth_yoy_pct` | % | same, net income; blank if base ≤ 0 | Mostly blank, same reason |
| `debt_to_equity` | ratio | prior-quarter total debt / stockholders' equity | Rebuilt; blank if equity ≤ 0 |
| `beta_252d` | ratio | slope of daily stock on SPY returns, 252 sessions to day −1 (min 200) | Rebuilt from prices |
| `return_52w_pct` | % | adjusted close day −1 vs 252 sessions earlier | Rebuilt |
| `ma50_ma200_gap_pct` | % | (50-day − 200-day mean adjusted close) / 200-day mean | Rebuilt |
| `avg_daily_volume_63d` | shares | mean volume, 63 sessions to day −1 | Rebuilt |
| `forward_pe` | — | — | **Excluded:** Yahoo has only a current snapshot |
| `short_interest_pct_float` | — | — | **Excluded:** Yahoo has only a current snapshot |

Choices made here that Cammy did not specify (flag for review): quarterly
rather than trailing-12-month margin; 63-session volume window; 252-session
beta against SPY; class A share class kept for dual listings.

Known limitations: Yahoo statements may reflect later restatements; Yahoo
labels quarters by calendar month end, matched to SEC period ends within 10
days; the share-count series is assumed to be as reported.

## Rebuild

```bash
pip install -r requirements.txt
export SEC_USER_AGENT="Name contact-email"     # SEC fair-access requirement
python code/gus_collect.py manifest  --as-of 2026-11-13
python code/gus_collect.py event-study --as-of 2026-11-13
python code/gus_collect.py features  --as-of 2026-11-13
python -m unittest discover -s tests
```

Raw downloads are cached in `data/raw/` (git-ignored) and are not committed.
