# Analysis Plan: Earnings Calls and Abnormal Returns

Team Magic

> **Frozen specification:** the variables, sample rules and tests that were actually run are in `specs_tried.md` §1–5 and Amendments 1–5. Where this plan differs, `specs_tried.md` governs. Results: `specs_tried.md` §8.

This plan sets out how we will test whether earnings-call language helps explain abnormal stock returns beyond what conventional earnings data already tell us, for S&P 500 companies reporting for the quarter ending in calendar Q2 2026. It covers the outcome, the sample, the three model runs and their variables, and how the models will be evaluated.

## Outcome

For this checkpoint, the outcome (Y) is **CAR[0,1]**: the cumulative abnormal return over the earnings call day and the following day, relative to what a factor model predicts. It is produced by the event study package from the list of tickers and call dates.

CAR[0,1] is the **primary outcome** of the study (`specs_tried.md` §3, frozen 2026-11-22). The cumulative abnormal return over the 20 trading sessions after the announcement-reaction session is a **secondary** outcome; it is not computed for the Q2 2026 cohort, and no reported result uses it.

## Sample and data

- **Observation:** one company-quarter earnings call.
- **Universe:** S&P 500 constituents as of June 30, 2026, from a dated roster file saved in the repo.
- **Period:** companies with fiscal quarters ending April 1 through June 30, 2026.
- **Same sample in every run:** all three runs use exactly the same events. Events missing any variable are dropped, and we report how many. A missing score is recorded as null, not zero, because zero would be read as a neutral score.
- **Main and robustness samples:** the main run uses events flagged `primary_timing_sample = True`. As a robustness check, we repeat the analysis on all events.
- **Inputs:** (1) the event study dataset, built from tickers and call dates, which supplies CAR[0,1]; (2) Yahoo Finance variables measured as of the call date; (3) a transcript dataset with one row per call. The three are merged on a shared event ID (event ID, ticker, and fiscal period end).

## Approach: three runs, each adding information

We run the same analysis three times on the same sample, adding variables each time. Because each run contains the previous one, any improvement can be credited to the variables added.

### Run 1: Yahoo Finance variables only

We model CAR[0,1] using the earnings surprise and firm characteristics available from Yahoo Finance. Every variable is measured as of the last trading day before the call, using price history through that date and the most recent quarterly financials reported before it.

**As run (`specs_tried.md` §4):** five variables: EPS surprise (%), log market cap, price-to-book, 52-week price change and beta. The longer candidate list below was narrowed before any fit; the other fields stay in the dataset but are not in the models.

- **Earnings news:** EPS surprise in dollars and as a percentage (actual minus consensus). Markets price in expectations, so the gap between actual and expected earnings is what should move the stock.
- **Size and valuation:** log market cap, price-to-book, forward P/E. Smaller and higher-valuation firms tend to react differently to the same news, since less is known about them or more is expected of them.
- **Profitability and quality:** profit margin, revenue growth, quarterly earnings growth. Steadier, faster-growing firms may get more credit for a surprise.
- **Leverage:** debt-to-equity. Leveraged firms have more fragile earnings, so news can move them more.
- **Risk and momentum:** beta, 52-week price change, gap between the 50-day and 200-day averages. A stock's usual volatility and prior run-up affect how much of the news is already priced in.
- **Attention and positioning:** average daily volume, short interest as a percentage of float. Liquidity and short interest affect how quickly and how sharply a stock responds.

We exclude announcement-day prices and volumes, which overlap with the outcome. Forward P/E and short interest are available from Yahoo mostly as current snapshots, so they are flagged as limitations and may be dropped.

### Run 2: Run 1 plus basic text measures (no AI)

We add measures computed from the call transcript without AI:

- Overall transcript sentiment
- Management sentiment (prepared remarks)
- Analyst question sentiment
- Uncertainty-word proportion
- Whether an analyst says "congratulations" (yes or no)

Sentiment uses the Loughran–McDonald dictionary on the Capital IQ speaker-tagged transcript sections (`code/build_dictionary_features.py`). The sentiment gap (management minus analyst questions) is **not** in the model: it is an exact combination of two Run 2 variables, so it is reported only as exploratory (Amendment 5). This run shows how much standard text analysis adds beyond the Yahoo Finance baseline.

### Run 3: Run 2 plus AI-extracted measures

We add five variables scored by a language model from the transcript only (prompt v2.0; scored by Gemma 4 on the course lead's computer, Amendment 5):

- **Guidance specificity:** whether forward guidance is absent, qualitative, or numeric (scored 0 to 2)
- **Guidance revision:** whether management cut, kept, or raised its prior guidance, as stated on the call (scored −1, 0, or +1, entered as one variable). Calls with no prior guidance to compare are dropped from the main run; a robustness run keeps them as their own category.
- **Q&A evasiveness:** how often management fails to directly answer analysts' questions (scored 0 to 2)
- **One-off attribution:** whether management credits or blames the quarter's results on temporary, one-time factors (scored −1, 0, or +1)
- **Analyst concern focus:** whether analysts' questions focus on a single problem the company has (scored 0 to 2)

A word-count method cannot do this work: telling vague guidance from a specific dollar range, matching each answer to its question, and understanding what is being compared with what all require a language model. Outlook tone was dropped because it largely re-measures sentiment. This run shows whether AI-based reading of the call adds predictive power beyond Runs 1 and 2.

## Method

- **Primary method: OLS regression.** It shows which variables matter, in which direction, and by how much. It is also easy to explain, and it suits a sample of this size.
- **Inference:** standard errors clustered by day 0; a block Wald test for each added block; on the holdout, a week-block bootstrap of the change in MSE and a shuffled-score placebo (`specs_tried.md` §5). The ridge/random-forest robustness idea was not adopted.
- **Evaluation:** sort events by announcement date, fit on the earlier 60%, and evaluate once on the later 40%. For each run we report out-of-sample R-squared, mean absolute error, and root mean squared error.

We fix the variables, models, and the 60/40 split before viewing any results, and we evaluate the later 40% only once. No variables are added or dropped after seeing holdout performance.

## Pipeline sketch

1. Build the event list: tickers and call dates for the sample.
2. Compute CAR[0,1] for each event with the event study package.
3. Collect the Run 1 variables as of the last trading day before each call.
4. Merge in the transcript variables (Runs 2 and 3) by event ID.
5. Sort events by call date and fit each run on the earlier 60%.
6. Evaluate each run once on the later 40% and compare out-of-sample R-squared, MAE, and RMSE.

## Data caveats

- **Real transcripts, kept local.** Runs 2–3 use the course's S&P Capital IQ transcripts. They stay in git-ignored `restricted_data/`; only numeric features and scores are committed. Synthetic transcripts were used only to test the pipeline and the prompt.
- **Look-ahead bias.** Yahoo Finance reports some fields only as current values. Variables must be rebuilt as of the day before each call, and any that cannot be are dropped or flagged.
- **LLM leakage.** For the AI-extracted variables, the scoring process must not use what the model may already know about how the stock reacted. The prompt and model version are recorded with every score.
- **Call timing and exclusions under verification.** The timing of each call and the earnings-announcement (EA) exclusion are still being verified, which is why the main run uses the `primary_timing_sample` flag.
- **Consensus EPS may not be point-in-time.** The EPS surprise uses a consensus estimate that is not yet confirmed to be the figure available before the call. Until it is, the surprise variable may carry look-ahead bias.
