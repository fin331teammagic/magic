"""Team Magic research dashboard: earnings calls and post-earnings returns.

Run from the repository root:

    streamlit run dashboard/pead_app.py

Presentation only. Data collection and estimation live in the pipeline and
statistics workstreams; this app reads their files through
``data_registry.py`` and never fills, zeroes, or invents values.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

import charts  # noqa: E402
from data_registry import (  # noqa: E402
    DATASETS,
    PILOT,
    REPO_ROOT,
    STATUS_LABELS,
    SYNTHETIC,
    language_feature_columns,
    load_dataset,
)
from status import (  # noqa: E402
    MATRIX_COLUMNS,
    STATUS_DEFINITIONS,
    STATUS_ORDER,
    STATUS_STYLE,
    build_status_matrix,
    coverage_funnel,
    sector_representation,
)

# Proposed (not team-agreed) holdout size below which results are labelled
# exploratory. Confirm with the statistics workstream.
MIN_HOLDOUT_FOR_CONFIRMATORY = 30

st.set_page_config(
    page_title="Earnings Calls & Post-Earnings Returns",
    page_icon="📈",
    layout="wide",
)

st.markdown(
    """
<style>
.block-container {padding-top: 2rem; max-width: 1400px;}
.status-chip {display:inline-block; padding:2px 10px; border-radius:999px;
  font-size:0.85rem; font-weight:600; margin:2px 6px 2px 0;}
.lede {font-size:1.05rem; line-height:1.55;}
.small-muted {color:#898781; font-size:0.85rem;}
</style>
""",
    unsafe_allow_html=True,
)


def status_chip(status: str) -> str:
    style = STATUS_STYLE[status]
    return '<span class="status-chip" style="background:{};color:{}">{} {}</span>'.format(
        style["color"], style["ink"], style["icon"], status
    )


def synthetic_banner(what: str = "This section"):
    st.error(
        "**SYNTHETIC TEST DATA: NOT RESEARCH RESULTS.** {} uses synthetic inputs "
        "generated to test the layout. Tickers starting with SYN are fake. Real "
        "outputs will replace them automatically when delivered.".format(what),
        icon="🧪",
    )


def pilot_banner():
    st.warning(
        "**PILOT DATA.** Four-company convenience sample (AAPL, MSFT, NVDA, TSLA) "
        "used to check the pipeline. It is not representative and is not evidence "
        "about the S&P 500 Q2 2026 cohort.",
        icon="⚠️",
    )


def awaiting(owner: str, what: str, items: list, files: list):
    with st.container(border=True):
        st.markdown("#### ⏳ Awaiting {}".format(owner))
        st.markdown(what)
        st.markdown("**What will appear here:**\n" + "\n".join("- " + i for i in items))
        st.markdown(
            "<span class='small-muted'>Expected file(s): {}. See "
            "<code>docs/DATA_CONTRACT_PROPOSAL.md</code>.</span>".format(
                ", ".join("<code>{}</code>".format(f) for f in files)
            ),
            unsafe_allow_html=True,
        )


def fmt_count(value):
    return "Pending" if value is None or pd.isna(value) else "{:,}".format(int(value))


# --------------------------------------------------------------------------
# Sidebar and data loading
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Team Magic · FIN331")
    st.caption("Earnings calls and post-earnings returns")
    use_fixtures = st.toggle(
        "Preview with synthetic test fixtures",
        value=False,
        key="use_fixtures",
        help="Fills the Findings tab with random SYNTHETIC data from tests/fixtures "
        "so the layout can be reviewed. Real files always take priority.",
    )

data = {key: load_dataset(key, allow_fixture=use_fixtures) for key in DATASETS}
cohort, pilot = data["cohort"], data["pilot"]
if cohort.available:
    events_ds = cohort
else:
    events_ds = pilot
events = events_ds.frame if events_ds.available else None
events_is_synthetic = events_ds.status == SYNTHETIC
roster = data["roster"].frame if data["roster"].available else None
audit = data["transcript_audit"].frame if data["transcript_audit"].available else None
screen = data["transcript_screen"].frame if data["transcript_screen"].available else None

with st.sidebar:
    st.divider()
    st.markdown("**Data sources**")
    for key, ds in data.items():
        if key == "synthetic_events" and ds.source == "absent":
            continue
        if ds.error or ds.missing_columns:
            icon, note = "❌", "problem loading; see Data quality tab"
        elif ds.source == "absent":
            icon, note = "⏳", "awaiting {}".format(ds.spec.owner)
        elif ds.status == SYNTHETIC:
            icon, note = "🧪", "{} rows · synthetic".format(ds.n_rows)
        elif ds.status == PILOT:
            icon, note = "⚠️", "{} rows · pilot".format(ds.n_rows)
        else:
            icon, note = "✅", "{} rows · {}".format(ds.n_rows, STATUS_LABELS[ds.status].lower())
        st.markdown("{} **{}**  \n<span class='small-muted'>{}</span>".format(icon, ds.spec.label, note),
                    unsafe_allow_html=True)
    if events is not None and "retrieved_at_utc" in events.columns:
        st.divider()
        st.caption("Event data retrieved: {}".format(str(events["retrieved_at_utc"].dropna().max())[:10]))

# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------
st.title("Earnings Calls and Post-Earnings Returns")
st.markdown(
    "<p class='lede'>Do variables measured from the earnings call, first with dictionary text "
    "analysis and then with an LLM, explain and predict the stock's abnormal return around the "
    "call (<b>CAR[0,1]</b>) <b>beyond</b> the EPS surprise and other standard fundamentals?</p>",
    unsafe_allow_html=True,
)
if events_ds is pilot:
    pilot_banner()
if use_fixtures:
    st.info(
        "Synthetic fixture preview is **on**. Affected sections carry a red "
        "SYNTHETIC banner. Turn it off in the sidebar before presenting.",
        icon="🧪",
    )

def count_llm_scored(path=REPO_ROOT / "outputs/llm_scores_real/q2_2026_llm_scores_v2.0_gemma4_all474.csv"):
    try:
        return int((pd.read_csv(path)["parse_status"] == "ok").sum())
    except Exception:  # file absent: show Pending
        return float("nan")


n_llm_scored = count_llm_scored()

MODEL_VARIABLES = {
    "eps_surprise_pct": "EPS surprise (%)",
    "log_market_cap": "Log market cap",
    "price_to_book": "Price-to-book",
    "return_52w_pct": "52-week return (%)",
    "beta_252d": "Beta",
    "transcript_sentiment": "Sentiment, whole call",
    "management_prepared_sentiment": "Sentiment, prepared remarks",
    "analyst_question_sentiment": "Sentiment, analyst questions",
    "uncertainty_word_proportion": "Uncertainty words",
    "congratulations_mentioned": "Analyst said 'congratulations'",
    "guidance_specificity": "AI: guidance specificity",
    "guidance_revision": "AI: guidance revision",
    "qa_evasiveness": "AI: Q&A evasiveness",
    "one_off_attribution": "AI: one-off attribution",
    "analyst_concern_focus": "AI: analyst concern focus",
}
# The correlation file uses the spec's names for two Run 1 variables.
CORR_NAMES = {**MODEL_VARIABLES, "price_change_52w_pct": "52-week return (%)", "beta": "Beta"}


@st.cache_data
def real_model_frame():
    """The Runs 1-3 primary sample, rebuilt with pandas from committed outputs.

    Same filters as code/run_nested_models.py: primary timing, call after the
    2026-06-30 cutoff, day 0 consistent with the call, parsed LLM scores, and
    every variable present (complete case). Returns None if a file is missing.
    """
    out = REPO_ROOT / "outputs"
    try:
        cohort = pd.read_csv(out / "q2_2026_cohort.csv")
        text = pd.read_csv(out / "q2_2026_dictionary_features.csv")
        day0 = pd.read_csv(out / "q2_2026_day0_transcript_check.csv")[["event_id", "day0_check"]]
        llm = pd.read_csv(out / "llm_scores_real" / "q2_2026_llm_scores_v2.0_gemma4_after_cutoff395.csv")
    except Exception:
        return None
    llm = llm[(llm["parse_status"] == "ok") & (llm["status"] == "scored")].rename(columns={"id": "event_id"})
    run1 = ["eps_surprise_pct", "log_market_cap", "price_to_book", "return_52w_pct", "beta_252d"]
    run2 = list(MODEL_VARIABLES)[5:10]
    run3 = list(MODEL_VARIABLES)[10:15]
    frame = (cohort[["event_id", "ticker", "day0_session", "primary_timing_sample", "car_0_1_pct"] + run1]
             .merge(text[["event_id", "after_training_cutoff"] + run2], on="event_id", how="left")
             .merge(day0, on="event_id", how="left")
             .merge(llm[["event_id"] + run3], on="event_id", how="left"))
    frame = frame[(frame["primary_timing_sample"] == True) & (frame["after_training_cutoff"] == True)  # noqa: E712
                  & (frame["day0_check"] == "consistent_with_call")]
    frame = frame.dropna(subset=["car_0_1_pct"] + run1 + run2 + run3)
    return frame.drop(columns=["primary_timing_sample", "after_training_cutoff", "day0_check"]).reset_index(drop=True)


SAMPLE_LABELS = {
    "primary": "Primary (304)",
    "all_events": "All timing events",
    "primary_null_category": "No-guidance as category",
    "primary_all_calls": "All 474 calls",
}

tabs = st.tabs(
    ["Overview", "Results (checkpoint)", "Data coverage", "Data quality & gaps", "Event explorer",
     "Language findings", "Methods & limitations"]
)
results_tab = tabs[1]
tabs = [tabs[0]] + list(tabs[2:])  # the original sections keep their indices below

# --------------------------------------------------------------------------
# 1. Overview
# --------------------------------------------------------------------------
with tabs[0]:
    funnel = coverage_funnel(
        roster,
        cohort.frame if cohort.available else None,
        audit,
        data["features"].frame if data["features"].available and data["features"].source == "real" else None,
        data["metrics"].frame if data["metrics"].available and data["metrics"].source == "real" else None,
    )
    stage = dict(zip(funnel["stage"], funnel["count"]))
    m = st.columns(4)
    m[0].metric("Roster stocks", fmt_count(stage["Roster stocks (June 30, 2026)"]), border=True,
                help="S&P 500 constituents on the archived June 30, 2026 list.")
    m[1].metric("Verified Q2 2026 events", fmt_count(stage["Verified Q2 2026 events"]), border=True,
                help="Pending until the verified event manifest and cohort output are delivered.")
    m[2].metric("Calls scored by AI", fmt_count(n_llm_scored), border=True,
                delta="474 matched to the cohort", delta_color="off", delta_arrow="off",
                help="Course-provided Capital IQ transcripts, scored by the course lead on a local model "
                     "(Gemma 4); no transcript text is in this repo.")
    m[3].metric("Model comparison", "Pending" if not (data["metrics"].available and data["metrics"].source == "real")
                else "Delivered", border=True)

    st.subheader("How the study works")
    steps = st.columns(4)
    step_text = [
        ("1 · Sample", "One observation = one company's quarterly earnings announcement. "
         "Universe: the S&P 500 list as of **June 30, 2026**, for fiscal quarters ending "
         "April 1 – June 30, 2026."),
        ("2 · Outcome", "**CAR[0,1]**: the abnormal return on the call's day 0 and day 1, i.e. "
         "the return not explained by the Fama–French five factors. The 20-session drift after "
         "the reaction is a secondary outcome."),
        ("3 · Run 1: fundamentals", "Explain and predict that outcome from what is known before "
         "the call: **EPS surprise**, size, price-to-book, 52-week momentum and beta."),
        ("4 · Runs 2–3: language", "Add **dictionary text measures** (Run 2), then "
         "**LLM-measured variables** (Run 3). Fit on the earliest 60% of events, test once on "
         "the latest 40%. Does each layer add anything?"),
    ]
    for col, (head, body) in zip(steps, step_text):
        with col.container(border=True, height="stretch"):
            st.markdown("**{}**".format(head))
            st.markdown(body)

    st.subheader("Workstream status")
    rows = []
    for key in ["roster", "pilot", "cohort", "exclusions", "transcript_screen", "transcript_audit",
                "features", "metrics", "holdout"]:
        ds = data[key]
        if ds.source == "absent":
            state = "⏳ Awaiting delivery"
        elif ds.error or ds.missing_columns:
            state = "❌ Delivered with problems"
        elif ds.source == "fixture":
            state = "🧪 Synthetic fixture (preview)"
        else:
            state = "✅ Delivered"
        rows.append({
            "Dataset": ds.spec.label,
            "Owner": ds.spec.owner,
            "State": state,
            "Data status": STATUS_LABELS[ds.status] if ds.source != "absent" else "—",
            "Rows": "—" if ds.n_rows is None else "{:,}".format(ds.n_rows),
            "What it is": ds.spec.description,
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True,
                 column_config={"What it is": st.column_config.TextColumn(width="large")})

    with st.expander("Glossary for readers new to the project"):
        st.markdown(
            """
- **EPS surprise:** `(reported EPS − consensus EPS) / |consensus EPS|`, in percent.
- **Announcement reaction:** the abnormal return on the first trading session that could react to the news.
- **Abnormal return:** the part of a stock's return not explained by a benchmark model.
- **ETF factor proxies:** market excess (SPY − BIL), size (IWM − SPY), value (IWD − IWF). These
  stand in for the Kenneth French factors, which lag recent events. *They are not the official French factors.*
- **SPY buy-and-hold abnormal return:** stock return minus SPY return over the same sessions; a simpler robustness check.
- **Post-earnings announcement drift (PEAD):** the documented tendency of prices to keep moving
  in the direction of an earnings surprise. The project does not try to rediscover it; it asks whether call language adds to it.
- **Chronological holdout:** the model is fit on earlier announcements and evaluated once on later ones, so it never "sees the future".
- **Out-of-sample R²:** improvement over simply predicting the training-set average. Below 0 means worse than that average.
"""
        )

# --------------------------------------------------------------------------
# 1b. Results (checkpoint): three nested runs on CAR[0,1]
# --------------------------------------------------------------------------
with results_tab:
    final_ds, runs_ds = data["final_dataset"], data["model_runs"]
    coefs_ds, preds_ds, vars_ds = data["model_coefficients"], data["run_predictions"], data["variables"]
    st.subheader("Does earnings-call language explain the stock's reaction?")
    st.markdown(
        "**Primary outcome: CAR[0,1]**, the cumulative abnormal return on the call day and the next "
        "trading day (`specs_tried.md` §3). The abnormal return over the 20 trading sessions after the "
        "reaction session is a secondary outcome."
    )
    names = {}
    if vars_ds.available:
        names = dict(zip(vars_ds.frame["variable"], vars_ds.frame["variable"].str.replace("_", " ")))
    if not runs_ds.available:
        awaiting("Runs 1-3", "The model runs are not available.",
                 ["Run 1 to 3 holdout R², MAE and RMSE", "Which variables move CAR[0,1]",
                  "Predicted vs. actual reactions"],
                 [DATASETS["model_runs"].path])
    else:
        all_runs = runs_ds.frame
        if runs_ds.status == SYNTHETIC:
            synthetic_banner("The model runs below")
        samples = list(dict.fromkeys(all_runs["sample"])) if "sample" in all_runs.columns else [None]
        sample = samples[0]
        if len(samples) > 1:
            sample = st.segmented_control(
                "Sample", samples, default=samples[0], required=True, key="runs_sample",
                format_func=lambda v: SAMPLE_LABELS.get(v, v),
                help="Primary is the pre-specified result. The others are robustness checks "
                     "(specs_tried.md Amendment 5).")

        def pick(frame):
            if frame is None or sample is None or "sample" not in frame.columns:
                return frame
            return frame[frame["sample"] == sample]

        runs = pick(all_runs).sort_values("run")
        first, last = runs.iloc[0], runs.iloc[-1]
        if runs_ds.status != SYNTHETIC and "delta_mse_vs_previous" in runs.columns:
            supported = runs["supported"].eq(True).any()
            parts = []
            for _, r in runs[runs["run"] > 1].iterrows():
                block = "the dictionary block (Run 2)" if r["run"] == 2 else "the AI block (Run 3)"
                parts.append("{} is {} in-sample (Wald p = {:.4f}) and makes holdout predictions **{}**".format(
                    block, "jointly significant" if r["block_wald_p"] < 0.05 else "not significant",
                    r["block_wald_p"], "better" if r["delta_mse_vs_previous"] > 0 else "worse"))
            st.info(
                "**Answer (pre-specified test):** the language variables are **{}**. {}. Holdout R² by run: "
                "{}.".format("supported" if supported else "not supported", (lambda t: t[:1].upper() + t[1:])("; ".join(parts)),
                             " → ".join("{:.3f}".format(v) for v in runs["out_of_sample_r2"])),
                icon="📌")

        k = st.columns(4)
        k[0].metric("Events used", "{:,}".format(int(first["train_n"] + first["test_n"])), border=True,
                    delta="{:,} excluded".format(int(first["excluded_n"])), delta_color="off", delta_arrow="off",
                    help="Same events in every run. Events missing any variable are dropped, never zero-filled.")
        k[1].metric("Training / holdout", "{} / {}".format(int(first["train_n"]), int(first["test_n"])),
                    border=True, help="Sorted by day 0: fit on the earliest 60%, tested once on the latest 40%.")
        if "in_sample_r2" in runs.columns:
            k[2].metric("In-sample R², Run 3", "{:.3f}".format(last["in_sample_r2"]), border=True,
                        delta="{:+.3f} vs. Run 1".format(last["in_sample_r2"] - first["in_sample_r2"]))
        k[3].metric("Holdout R², Run 3", "{:.3f}".format(last["out_of_sample_r2"]), border=True,
                    delta="{:+.3f} vs. Run 1".format(last["out_of_sample_r2"] - first["out_of_sample_r2"]))

        st.markdown("#### Does each layer of information improve prediction?")
        st.caption("Each run adds variables to the previous one, on the same events. Higher R² and lower error "
                   "mean better holdout predictions. Below 0 R² means worse than guessing the training average.")
        st.altair_chart(charts.run_metrics_chart(runs))
        st.caption("Runs: **1** EPS surprise, size, price-to-book, 52-week return, beta · **2** + dictionary "
                   "sentiment (whole call, prepared remarks, analyst questions), uncertainty words, analyst "
                   "'congratulations' · **3** + AI-scored guidance specificity, guidance revision, Q&A "
                   "evasiveness, one-off attribution, analyst concern focus. Training: day 0 through {}. "
                   "Holdout: from {}.".format(first["train_cutoff"], first["test_start"]))
        if "block_wald_p" in runs.columns:
            tests = runs[runs["run"] > 1].assign(
                comparison=lambda d: d["run"].map({2: "Run 2 vs. 1", 3: "Run 3 vs. 2"}))
            st.dataframe(
                tests[["comparison", "block_wald_p", "delta_mse_vs_previous", "delta_mse_ci_low",
                       "delta_mse_ci_high", "placebo_share_at_least_actual", "bootstrap_weeks"]],
                hide_index=True, column_config={
                    "comparison": "Comparison",
                    "block_wald_p": st.column_config.NumberColumn("In-sample Wald p", format="%.4f"),
                    "delta_mse_vs_previous": st.column_config.NumberColumn(
                        "Holdout MSE gain", format="%.2f", help="Positive = the added block predicts better."),
                    "delta_mse_ci_low": st.column_config.NumberColumn("95% low", format="%.2f"),
                    "delta_mse_ci_high": st.column_config.NumberColumn("95% high", format="%.2f"),
                    "placebo_share_at_least_actual": st.column_config.NumberColumn(
                        "Placebo share ≥ actual", format="%.2f",
                        help="Share of 1,000 shuffled-score runs that did at least as well. Small = real signal."),
                    "bootstrap_weeks": st.column_config.NumberColumn("Holdout weeks", format="%d"),
                })
            st.caption("The holdout spans only {} calendar weeks of day 0, so the bootstrap interval resamples "
                       "very few blocks and is not reliable on its own; the placebo share is the steadier "
                       "guide.".format(int(tests["bootstrap_weeks"].max())))

        a, b = st.columns([3, 2], gap="large")
        with a:
            st.markdown("#### Which variables matter? (in-sample)")
            if coefs_ds.available:
                run_id = st.segmented_control("Model", list(runs["run"]), default=int(last["run"]),
                                              format_func=lambda r: "Run {}".format(r), required=True,
                                              key="coef_run")
                coefs = pick(coefs_ds.frame)
                st.altair_chart(charts.coefficient_chart(coefs[coefs["run"] == run_id], names), width="stretch")
                st.caption("Dot = estimated change in CAR[0,1] (percentage points) when the variable rises by "
                           "one standard deviation, holding the others fixed. Line = 95% interval, standard "
                           "errors clustered by day 0. Guidance specificity is 2 for 298 of 304 primary "
                           "events, so its estimate rests on 6 calls.")
        with b:
            st.markdown("#### Predicted vs. actual (holdout)")
            if preds_ds.available:
                choice = st.selectbox("Model", list(runs["label"]), index=len(runs) - 1, key="pred_run")
                run_id = int(runs.loc[runs["label"] == choice, "run"].iloc[0])
                st.altair_chart(charts.run_predictions_chart(pick(preds_ds.frame), "pred_run{}".format(run_id),
                                                             choice), width="stretch")
                st.caption("Points on the dashed line are perfect predictions.")

    model_frame = real_model_frame()
    if model_frame is not None:
        st.divider()
        st.markdown("#### Explore one variable against the reaction (real data)")
        st.caption("The {:,} primary events used in Runs 1–3: CAR[0,1] against each pre-specified "
                   "predictor. These are raw associations, not the controlled estimates above.".format(
                       len(model_frame)))
        e1, e2 = st.columns([3, 2], gap="large")
        with e1:
            xvar = st.selectbox("Variable", list(MODEL_VARIABLES), index=0,
                                format_func=lambda v: MODEL_VARIABLES[v], key="real_explore_var")
            if model_frame[xvar].nunique() <= 5:
                st.altair_chart(charts.group_mean_chart(
                    model_frame.assign(**{xvar: model_frame[xvar].astype(int).astype(str)}),
                    xvar, "car_0_1_pct", "CAR[0,1] (%)"), width="stretch")
                counts = model_frame[xvar].astype(int).value_counts().sort_index()
                st.caption("Calls per score: " + ", ".join("{} → {}".format(k, v) for k, v in counts.items()))
            else:
                st.altair_chart(charts.binned_relationship_chart(
                    model_frame, xvar, MODEL_VARIABLES[xvar], "car_0_1_pct", "CAR[0,1] (%)"), width="stretch")
        with e2:
            st.markdown("**Average reaction: beat vs. miss**")
            grp = model_frame.assign(result=(model_frame["eps_surprise_pct"] > 0).map(
                {True: "Beat consensus", False: "Missed / met"}))
            st.altair_chart(charts.group_mean_chart(grp, "result", "car_0_1_pct", "CAR[0,1] (%)"), width="stretch")
            st.markdown("**Average reaction: guidance revision (AI-scored)**")
            grp = model_frame.assign(guidance=model_frame["guidance_revision"].map(
                {-1: "Lowered", 0: "Maintained", 1: "Raised"}))
            st.altair_chart(charts.group_mean_chart(grp, "guidance", "car_0_1_pct", "CAR[0,1] (%)"),
                            width="stretch")

        with st.expander("Do the AI variables just re-measure what we already had? (the 'ruler' check)"):
            corr_path = REPO_ROOT / "outputs" / "run3_feature_correlations.csv"
            if corr_path.exists():
                corr = pd.read_csv(corr_path, index_col=0)
                corr = corr[[c for c in corr.columns if c not in corr.index]]
                corr = corr.rename(index=CORR_NAMES, columns=CORR_NAMES)
                st.dataframe(corr, column_config={
                    c: st.column_config.NumberColumn(format="%.2f") for c in corr.columns})
                st.caption("Spearman correlations on the 304 primary events. No AI variable correlates above "
                           "0.31 in absolute value with EPS surprise or any dictionary measure, so they measure "
                           "something different. Guidance specificity is 2 for 298 of 304 calls, so it barely "
                           "varies.")
        with st.expander("Model dataset ({:,} rows, numbers only)".format(len(model_frame))):
            st.dataframe(model_frame, hide_index=True)
            st.download_button("Download (CSV)", model_frame.to_csv(index=False).encode(),
                               "runs_1_3_primary_sample.csv", mime="text/csv")

# --------------------------------------------------------------------------
# 2. Data coverage
# --------------------------------------------------------------------------
with tabs[1]:
    st.subheader("From universe to usable observations")
    st.caption(
        "Each bar is a stage the data must pass. A stage reads **Pending** until its owner "
        "delivers the file; it is never filled with a placeholder number. A real zero is shown as 0."
    )
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.altair_chart(charts.coverage_funnel_chart(funnel), width="stretch")
    with right:
        with st.container(border=True):
            st.markdown("**What share of the intended sample do we have?**")
            n_events = stage["Verified Q2 2026 events"]
            if pd.isna(n_events):
                st.markdown(
                    "Not yet measurable. The intended sample is every roster company whose "
                    "fiscal quarter ended in calendar Q2 2026. That is **not automatically all "
                    "503** (e.g. Apple's and Visa's fiscal quarters are offset), so the "
                    "denominator comes from Gus's verified event manifest and exclusion log."
                )
            else:
                excl = data["exclusions"]
                st.metric("Cohort events vs. roster", "{:.0%}".format(n_events / stage["Roster stocks (June 30, 2026)"]))
                if excl.available:
                    st.dataframe(excl.frame["reason"].value_counts().rename_axis("Exclusion reason")
                                 .reset_index(name="Stocks"), hide_index=True)
                else:
                    st.caption("Exclusion log not delivered, so excluded firms cannot yet be explained.")
            if pilot.available:
                st.markdown(
                    "<span class='small-muted'>The {} pilot events are a separate pipeline check "
                    "and are not counted in this funnel.</span>".format(len(pilot.frame)),
                    unsafe_allow_html=True,
                )

    st.subheader("Is transcript coverage representative across sectors?")
    if roster is not None:
        groups = {}
        if screen is not None:
            groups["Transcript listing leads"] = screen["ticker"].unique()
        if cohort.available:
            groups["Cohort events"] = cohort.frame["ticker"].unique()
        sectors = sector_representation(roster, groups)
        c1, c2 = st.columns([3, 2], gap="large")
        with c1:
            st.altair_chart(charts.sector_share_chart(sectors), width="stretch")
        with c2:
            if "Transcript listing leads" in groups:
                wide = sectors.pivot_table(index="sector", columns="group", values="share_pct").fillna(0)
                gap = (wide["Transcript listing leads"] - wide["Roster"]).sort_values()
                st.markdown(
                    "Bars compare each sector's share of the **roster** with its share of the "
                    "{} **transcript listing leads** screened so far.".format(len(groups["Transcript listing leads"]))
                )
                st.markdown(
                    "- Most over-represented: **{}** ({:+.0f} pp)\n"
                    "- Most under-represented: **{}** ({:+.0f} pp)".format(gap.index[-1], gap.iloc[-1],
                                                                       gap.index[0], gap.iloc[0])
                )
                st.caption(
                    "Leads came from a quick screen of large, widely covered firms, not a random draw. "
                    "If the language analysis only uses such firms, results may not generalise to the full index."
                )

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.subheader("When did announcements happen?")
        st.caption("Matters because the holdout split is chronological: later announcements form the test set.")
        if events is not None:
            if events_ds is pilot:
                st.caption("Showing **pilot** events.")
            st.altair_chart(charts.timeline_chart(events), width="stretch")
    with c2:
        st.subheader("Transcript access log")
        st.caption("Metadata only. No transcript text is stored in this project.")
        if audit is not None:
            show = audit[["ticker", "transcript_available", "transcript_source",
                          "retention_permission", "external_model_permission", "screened_at_utc"]]
            st.dataframe(show, hide_index=True, column_config={
                "ticker": "Ticker",
                "transcript_available": "Transcript located?",
                "transcript_source": "Source",
                "retention_permission": "May we retain it?",
                "external_model_permission": "May we send it to an AI model?",
                "screened_at_utc": "Checked on",
            })
        if screen is not None:
            st.caption("{} further tickers appear only as listing leads in the candidate screen.".format(
                len(set(screen["ticker"]) - set(audit["ticker"] if audit is not None else []))))

# --------------------------------------------------------------------------
# 3. Data quality and gaps
# --------------------------------------------------------------------------
with tabs[2]:
    st.subheader("Where are the gaps?")
    st.markdown("Every cell is classified into exactly one status. Missing values are never filled or treated as zero.")
    legend_cols = st.columns(3)
    for i, s in enumerate(STATUS_ORDER):
        with legend_cols[i % 3]:
            st.markdown("{}<br><span class='small-muted'>{}</span>".format(status_chip(s), STATUS_DEFINITIONS[s]),
                        unsafe_allow_html=True)

    problems = [ds for ds in data.values() if ds.error or ds.missing_columns]
    for ds in problems:
        st.error("**{}** ({}) could not be used: {}".format(
            ds.spec.label, ds.spec.path,
            ds.error or "missing required columns " + ", ".join(ds.missing_columns)))

    if events is None:
        awaiting("Gus (pipeline)", "No event-level file is available yet.", ["Status grid per event and field"],
                 [DATASETS["cohort"].path])
    else:
        features_ds = data["features"]
        features = features_ds.frame if features_ds.available and features_ds.source == "real" else None
        matrix = build_status_matrix(events, events_is_synthetic, audit, screen, features)
        if events_ds is pilot:
            st.caption("Showing the **pilot** events (the cohort output has not been delivered yet).")

        f1, f2 = st.columns([2, 3])
        only_gaps = f1.toggle("Show only events with a gap", value=False)
        tickers = sorted(matrix["ticker"].unique())
        chosen = f2.multiselect("Events", tickers, default=tickers if len(tickers) <= 30 else tickers[:30])
        view = matrix[matrix["ticker"].isin(chosen)]
        if only_gaps:
            gap_tickers = view.loc[view["status"] != "Available", "ticker"].unique()
            view = view[view["ticker"].isin(gap_tickers)]

        if view.empty:
            st.info("No events match the current filters.")
        else:
            st.altair_chart(charts.status_grid_chart(view), width="stretch")

        st.markdown("**Status mix by field (all events)**")
        st.altair_chart(charts.status_count_chart(matrix), width="stretch")

        missing_cols = [c for c in ("fiscal_period_end", "event_timestamp_source") if c not in events.columns]
        if missing_cols and events_ds is pilot:
            st.info(
                "The pilot file predates the pipeline's current output schema and lacks: "
                "{}. Regenerating it is a pipeline task (Gus).".format(", ".join(missing_cols)),
                icon="ℹ️",
            )

        wide = matrix.pivot_table(index="ticker", columns="field", values="status", aggfunc="first")
        wide = wide.reindex(columns=MATRIX_COLUMNS)
        with st.expander("Status table (download)"):
            st.dataframe(wide)
            st.download_button("Download status table (CSV)", wide.to_csv().encode(), "data_status_matrix.csv",
                               mime="text/csv")
        st.caption(
            "\"Not yet observable\" is estimated from weekdays between the announcement and the data's "
            "retrieval date (with a 3-session holiday buffer). An explicit pipeline flag would replace this "
            "approximation; see the data contract proposal."
        )

# --------------------------------------------------------------------------
# 4. Event explorer
# --------------------------------------------------------------------------
with tabs[3]:
    if events is None:
        awaiting("Gus (pipeline)", "No event-level file is available yet.",
                 ["EPS surprise vs. abnormal return", "Announcement reaction vs. forward drift"],
                 [DATASETS["cohort"].path])
    else:
        if events_ds is pilot:
            pilot_banner()
        df = events.copy()
        if roster is not None and "company" not in df.columns:
            df = df.merge(roster[["Symbol", "Security", "GICS Sector"]].rename(
                columns={"Symbol": "ticker", "Security": "company", "GICS Sector": "sector"}), on="ticker", how="left")
        CAR_METHOD = "CAR[0,1], Fama-French 5 (checkpoint)"
        methods = ([CAR_METHOD] if "car_0_1_pct" in df.columns else []) + [
            "ETF factor proxies (primary)", "SPY buy-and-hold (robustness)"]
        c1, c2, c3 = st.columns([2, 1, 2])
        method = c1.segmented_control("Return method", methods, default=methods[0], required=True)
    if events is not None and method == CAR_METHOD:
        f1, f2 = st.columns([1, 2])
        primary_only = f1.toggle("Primary timing sample only", value=True,
                                 help="SEC filing time and Yahoo agree on day 0. Gus recommends this sample for "
                                 "the main analysis; all events are a robustness check.")
        sectors = sorted(df["gics_sector"].dropna().unique()) if "gics_sector" in df.columns else []
        picked_sectors = f2.multiselect("Sectors", sectors, default=sectors)
        view = df.copy()
        if primary_only and "primary_timing_sample" in view.columns:
            view = view[view["primary_timing_sample"].astype(str).str.lower() == "true"]
        if sectors:
            view = view[view["gics_sector"].isin(picked_sectors)]
        car = view["car_0_1_pct"]
        k = st.columns(4)
        k[0].metric("Events shown", "{:,}".format(len(view)), border=True)
        k[1].metric("With CAR[0,1]", "{:,}".format(int(car.notna().sum())), border=True,
                    help="Blank when easy_es dropped the event (e.g. too few estimation days). Never zero-filled.")
        k[2].metric("Median CAR[0,1]", "—" if car.dropna().empty else "{:+.2f}%".format(car.median()), border=True)
        k[3].metric("Share positive", "—" if car.dropna().empty else "{:.0%}".format((car.dropna() > 0).mean()),
                    border=True)
        a, b = st.columns(2, gap="large")
        with a:
            st.markdown("**EPS surprise vs. CAR[0,1]**")
            st.altair_chart(charts.binned_relationship_chart(
                view.assign(eps_surprise_pct=view["eps_surprise_pct"].clip(-50, 50)),
                "eps_surprise_pct", "EPS surprise (%, capped at ±50 for display)", "car_0_1_pct", "CAR[0,1] (%)"),
                width="stretch")
            st.caption("Orange line is a simple straight-line fit for orientation, not the study's model. "
                       "Yahoo consensus is not point-in-time verified.")
        with b:
            st.markdown("**Day-0 vs. day-1 abnormal return**")
            st.altair_chart(charts.binned_relationship_chart(view, "ar_day0_pct", "Day-0 abnormal return (%)",
                                                             "ar_day1_pct", "Day-1 abnormal return (%)"),
                            width="stretch")
            st.caption("CAR[0,1] = day 0 + day 1. Shows whether the reaction continues or reverses the next day.")
        st.markdown("**Event-level data**")
        cols = [c for c in ["ticker", "company", "gics_sector", "fiscal_period_end", "earnings_timestamp",
                            "release_timing", "timing_check", "eps_actual", "eps_estimate", "eps_surprise_pct",
                            "ar_day0_pct", "ar_day1_pct", "car_0_1_pct", "car_0_1_status"] if c in view.columns]
        num = st.column_config.NumberColumn
        st.dataframe(view[cols].sort_values("earnings_timestamp"), hide_index=True, column_config={
            "ticker": "Ticker", "company": "Company", "gics_sector": "Sector",
            "fiscal_period_end": "Fiscal period end", "earnings_timestamp": "Release time (SEC 8-K)",
            "release_timing": "Timing", "timing_check": "Yahoo check",
            "eps_actual": num("EPS actual", format="%.2f"), "eps_estimate": num("EPS consensus", format="%.2f"),
            "eps_surprise_pct": num("EPS surprise", format="%.2f%%"),
            "ar_day0_pct": num("AR day 0", format="%.2f%%"), "ar_day1_pct": num("AR day 1", format="%.2f%%"),
            "car_0_1_pct": num("CAR[0,1]", format="%.2f%%"), "car_0_1_status": "CAR status"})
        st.download_button("Download shown events (CSV)", view.to_csv(index=False).encode(),
                           "q2_2026_cohort_filtered.csv", mime="text/csv")
        with st.expander("How CAR[0,1] is computed"):
            st.markdown(
                """
- **easy_es 0.1.8**, Fama-French 5-factor model (official Kenneth French daily factors), estimated over
  the window before each event. **CAR[0,1]** is the abnormal return on day 0 plus day 1.
- **Day 0** is the first trading session that could react: releases at or after 4:00 pm New York time map
  to the next session. Times come from the SEC 8-K Item 2.02 filing, checked against Yahoo.
- Blank cells mean the value is unavailable. They are never treated as zero.
- Details: `docs/GUS_DATA_DICTIONARY.md`.
"""
            )
    elif events is not None:
        horizon = c2.selectbox("Forward window", [20, 5, 60], format_func=lambda h: "{} sessions".format(h))
        tick_opts = sorted(df["ticker"].unique())
        picked = c3.multiselect("Companies", tick_opts, default=tick_opts)
        df = df[df["ticker"].isin(picked)]

        prefix = "factor_proxy_" if method.startswith("ETF") else ""
        fwd_col = "{}abnormal_{}d_return_pct".format(prefix, horizon)
        react_col = "{}announcement_abnormal_return_pct".format(prefix)
        method_short = "ETF-proxy" if prefix else "SPY buy-and-hold"
        fwd_title = "{}-session {} abnormal return (%)".format(horizon, method_short)

        if fwd_col not in df.columns or react_col not in df.columns:
            st.warning("This file does not contain {} / {}.".format(react_col, fwd_col))
        elif df.empty:
            st.info("Select at least one company.")
        else:
            n_missing = int(df[fwd_col].isna().sum())
            a, b = st.columns(2, gap="large")
            with a:
                st.markdown("**EPS surprise vs. {}**".format(fwd_title.lower()))
                st.altair_chart(charts.surprise_scatter(df, fwd_col, fwd_title), width="stretch")
            with b:
                st.markdown("**Day-0 reaction vs. the {}-session window that follows**".format(horizon))
                st.altair_chart(charts.reaction_vs_forward_chart(
                    df, react_col, fwd_col, "{}-session forward window".format(horizon)), width="stretch")
            if n_missing:
                st.caption("{} of {} events have no {}-session value (window incomplete or missing); "
                           "they are left out of the scatter, not set to zero.".format(n_missing, len(df), horizon))

            st.markdown("**Event-level data**")
            cols = [c for c in ["ticker", "company", "sector", "fiscal_period_end", "earnings_timestamp",
                                "eps_actual", "eps_estimate", "eps_surprise_pct", react_col,
                                "{}abnormal_5d_return_pct".format(prefix), "{}abnormal_20d_return_pct".format(prefix),
                                "{}abnormal_60d_return_pct".format(prefix), "earnings_source", "prices_source"]
                    if c in df.columns]
            num = st.column_config.NumberColumn
            st.dataframe(df[cols].sort_values("earnings_timestamp"), hide_index=True, column_config={
                "ticker": "Ticker",
                "company": "Company",
                "sector": "Sector",
                "fiscal_period_end": "Fiscal period end",
                "earnings_timestamp": "Announcement time",
                "eps_actual": num("EPS actual", format="%.2f"),
                "eps_estimate": num("EPS consensus", format="%.2f"),
                "eps_surprise_pct": num("EPS surprise", format="%.2f%%"),
                react_col: num("Day-0 reaction", format="%.2f%%"),
                "{}abnormal_5d_return_pct".format(prefix): num("5-session", format="%.2f%%"),
                "{}abnormal_20d_return_pct".format(prefix): num("20-session", format="%.2f%%"),
                "{}abnormal_60d_return_pct".format(prefix): num("60-session", format="%.2f%%"),
                "earnings_source": "Earnings source",
                "prices_source": "Price source",
            })

        with st.expander("How these numbers are computed"):
            st.markdown(
                """
- **ETF-proxy abnormal return:** each stock's daily excess return is regressed on SPY−BIL, IWM−SPY
  and IWD−IWF over the 252 sessions before the event. The day-0 residual is the announcement reaction;
  forward windows sum the residuals of the following sessions.
- **SPY buy-and-hold:** stock buy-and-hold return minus SPY's over the same sessions.
- Blank cells mean the value is unavailable or the window has not finished. They are never treated as zero.
- See `audits/01_self_audit.md` for the pilot's assumptions and limitations.
"""
            )

# --------------------------------------------------------------------------
# 5. Findings
# --------------------------------------------------------------------------
with tabs[4]:
    metrics_ds, holdout_ds, features_ds = data["metrics"], data["holdout"], data["features"]
    st.subheader("Does call language improve prediction?")
    st.markdown(
        "Both models are fit on the **earliest 60%** of events and evaluated once on the **latest 40%** "
        "(the holdout), using the same events. Lower error and higher out-of-sample R² mean better predictions."
    )
    if not metrics_ds.available:
        awaiting(
            "Cammy (statistics)",
            "The model comparison has not been delivered. No results are shown until it is.",
            ["Holdout MAE, RMSE and out-of-sample R² for the baseline vs. the language-augmented model",
             "Training and holdout sample sizes and the date of the split",
             "Predicted vs. actual returns for each holdout event",
             "An automatic **Exploratory** label if the holdout is small"],
            [DATASETS["metrics"].path, DATASETS["holdout"].path],
        )
        if not use_fixtures:
            st.caption("To review the layout now, switch on *Preview with synthetic test fixtures* in the sidebar.")
    else:
        if metrics_ds.status == SYNTHETIC:
            synthetic_banner("The model comparison below")
        mt = metrics_ds.frame.set_index("model")
        if "baseline" in mt.index and "with_language" not in mt.index:
            # Real Run 1 delivered before Runs 2-3 (specs_tried.md, amendment 1).
            base = mt.loc["baseline"]
            outcome = str(base.get("outcome", "car_0_1_pct"))
            st.info(
                "**Run 1 alone (fundamentals), on its full sample.** Runs 1–3 together, on the smaller "
                "transcript sample, are on the *Results* tab. Outcome: `{}`. Training calls through {}; holdout from {}.".format(
                    outcome, str(base.get("train_cutoff", ""))[:10], str(base.get("test_start", ""))[:10]),
                icon="📌",
            )
            k = st.columns(4)
            k[0].metric("Training / holdout events", "{} / {}".format(int(base["train_n"]), int(base["test_n"])),
                        border=True)
            k[1].metric("Holdout RMSE", "{:.2f} pp".format(base["rmse"]), border=True)
            k[2].metric("Out-of-sample R²", "{:.3f}".format(base["out_of_sample_r2"]), border=True,
                        help="Against the training-set mean. Below 0 means worse than predicting that mean.")
            if "in_sample_r2" in mt.columns:
                k[3].metric("In-sample R², Run 1", "{:.3f}".format(base["in_sample_r2"]),
                            border=True, help="Clustered Wald p = {:.4f} that all five slopes are zero.".format(
                                base["in_sample_wald_p"]))
            if "mse_gain_ci_low" in mt.columns:
                st.caption(
                    "MSE gain over the training-mean forecast: {:.2f}, week-block bootstrap 95% interval "
                    "[{:.2f}, {:.2f}] over {} holdout weeks (supplementary; see `specs_tried.md` §8).".format(
                        base["mse_gain_vs_train_mean"], base["mse_gain_ci_low"], base["mse_gain_ci_high"],
                        int(base["bootstrap_weeks"])))
            if holdout_ds.available:
                st.markdown("**Predicted vs. actual (holdout), Run 1**")
                st.altair_chart(charts.predicted_vs_actual_chart(
                    holdout_ds.frame, outcome_title="CAR[0,1] (%)" if outcome == "car_0_1_pct" else outcome),
                    width="stretch")
        elif not {"baseline", "with_language"}.issubset(mt.index):
            st.error("Metrics file must contain rows for models 'baseline' and 'with_language'.")
        else:
            base, lang = mt.loc["baseline"], mt.loc["with_language"]
            test_n, train_n = int(base["test_n"]), int(base["train_n"])
            if test_n < MIN_HOLDOUT_FOR_CONFIRMATORY:
                st.warning(
                    "**Exploratory:** the holdout has {} events (proposed minimum {}). Differences this "
                    "small-sample are not reliable evidence either way.".format(test_n, MIN_HOLDOUT_FOR_CONFIRMATORY),
                    icon="🔎",
                )
            k = st.columns(4)
            k[0].metric("Training / holdout events", "{} / {}".format(train_n, test_n), border=True)
            k[1].metric("Holdout RMSE, baseline", "{:.2f} pp".format(base["rmse"]), border=True)
            k[2].metric("Holdout RMSE, with language", "{:.2f} pp".format(lang["rmse"]),
                        delta="{:+.3f} pp vs. baseline".format(lang["rmse"] - base["rmse"]),
                        delta_color="inverse", border=True)
            k[3].metric("Out-of-sample R², with language", "{:.3f}".format(lang["out_of_sample_r2"]),
                        delta="{:+.3f} vs. baseline ({:.3f})".format(
                            lang["out_of_sample_r2"] - base["out_of_sample_r2"], base["out_of_sample_r2"]),
                        border=True, help="Below 0 means worse than predicting the training-set average.")
            if "train_cutoff" in mt.columns:
                st.caption("Training events up to {}; holdout from {}.".format(
                    str(base["train_cutoff"])[:10], str(base.get("test_start", ""))[:10]))
            a, b = st.columns(2, gap="large")
            with a:
                st.markdown("**Holdout prediction error**")
                st.altair_chart(charts.metric_comparison_chart(metrics_ds.frame), width="stretch")
            with b:
                st.markdown("**Predicted vs. actual (holdout)**")
                if holdout_ds.available:
                    if holdout_ds.status == SYNTHETIC and metrics_ds.status != SYNTHETIC:
                        synthetic_banner("This chart")
                    st.altair_chart(charts.predicted_vs_actual_chart(holdout_ds.frame), width="stretch")
                    st.caption("Points on the dashed line are perfect predictions.")
                else:
                    st.info("Holdout predictions file not delivered.")

    st.divider()
    st.subheader("Language variables")
    st.info("Runs 2–3 (dictionary and AI-scored language) and a real-data explorer of each language "
            "variable against CAR[0,1] are on the *Results* tab.", icon="➡️")

# --------------------------------------------------------------------------
# 6. Methods and limitations
# --------------------------------------------------------------------------
LIMITATIONS = {
    "Sample and selection": [
        ("Single reporting cohort",
         "Only fiscal quarters ending in calendar Q2 2026. Results describe one quarter's market "
         "environment and may not hold in other periods.", "README, STATUS"),
        ("Roster is not an official S&P file",
         "The June 30, 2026 list is an archived Wikipedia revision (1361794875). It is dated and "
         "fixed, but not a licensed index-provider record.", "README"),
        ("Fiscal calendars differ",
         "Some firms (e.g. Apple, Visa) have offset fiscal years; a reporting date does not imply a "
         "calendar-Q2 fiscal end. Each event's period end must be verified.", "README"),
        ("Transcript coverage and the training cutoff",
         "474 of 499 events matched a Capital IQ call; 25 did not (call after Aug 7, firm not "
         "covered, or no call). Runs 2–3 use only calls after June 30, 2026 with a day 0 that matches "
         "the call, so they rest on 304 of 499 events.", "specs_tried Amendments 2–3, 5"),
        ("Pilot is a convenience sample",
         "The four pilot firms were hand-picked to test the pipeline and carry no evidential weight.",
         "AGENTS, audit"),
    ],
    "Measurement": [
        ("ETF proxies are not French factors",
         "Market, size and value are proxied with SPY−BIL, IWM−SPY and IWD−IWF because official "
         "factor files lag. Proxy choice can change abnormal returns.", "README, audit"),
        ("EPS consensus and timestamps need verification",
         "Yahoo Finance does not preserve point-in-time consensus or reliable fiscal period ends. "
         "Cohort EPS and announcement times require documented sources.", "README, audit"),
        ("Announcement timing",
         "Before-open vs. after-close releases change which session is day 0. Errors shift returns "
         "between the reaction and the forward window.", "audit"),
    ],
    "Timing and confounding": [
        ("Incomplete forward windows",
         "Some 60-session windows were not finished as of November 6, 2026. They are reported as "
         "not yet observable, never as zero.", "STATUS, audit"),
        ("Overlapping windows and shared news",
         "Many firms report within weeks of each other, so their return windows overlap and share "
         "market news; events are not fully independent.", "audit"),
        ("Same-day confounding news",
         "Other news released with earnings (guidance, M&A, macro data) can drive returns.", "audit"),
    ],
    "Transcripts and AI scoring": [
        ("Licensed transcripts stay local",
         "Course-provided Capital IQ transcripts are kept out of the repo; only numeric scores are "
         "committed. The course lead scored them on his own computer, so no text went to an outside "
         "service.", "Amendment 5"),
        ("Model training-data cutoff",
         "Gemma 4's training data runs to January 2025 and the primary sample uses calls after June 30, "
         "2026, but a published cutoff does not prove specific events were absent from training data.",
         "Amendment 5"),
        ("One scoring run",
         "Scores come from a single temperature-0 run of one model; no repeat or second-model check "
         "on real calls. Guidance specificity is 2 for 98% of calls.", "Amendment 5"),
        ("Leakage controls",
         "Scores must be fixed and reproducible (pinned model, versioned prompt) and must not see "
         "later returns or post-call information.", "AGENTS"),
        ("Synthetic transcripts",
         "Early feature work uses synthetic transcripts to test the workflow. Their scores say "
         "nothing about real calls.", "Team plan"),
    ],
    "Inference and interpretation": [
        ("Short holdout",
         "The transcript data ends Aug 7, 2026, so the 40% holdout (113 events) spans only 2 calendar "
         "weeks of day 0. The week-block bootstrap then resamples 2 blocks and its intervals are not "
         "reliable on their own; the shuffled-score placebo is the steadier check.", "specs_tried §8"),
        ("Prediction ≠ profit",
         "A predictive association is not a trading strategy: no transaction costs, capacity or "
         "implementation are modelled. Nothing here is investment advice.", "STATUS, audit"),
    ],
}

with tabs[5]:
    st.subheader("What could make these results wrong?")
    st.markdown("Limitations grouped by where they enter the study. Sources point to the project documents "
                "that track each one (`README.md`, `STATUS.md`, `audits/01_self_audit.md`, `AGENTS.md`).")
    cols = st.columns(2, gap="large")
    for i, (group, items) in enumerate(LIMITATIONS.items()):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown("#### {}".format(group))
                for title, body, source in items:
                    st.markdown("**{}**: {}  \n<span class='small-muted'>Source: {}</span>".format(
                        title, body, source), unsafe_allow_html=True)

    st.subheader("Data provenance")
    prov = []
    for key, ds in data.items():
        if ds.source == "absent":
            continue
        retrieved = ""
        if ds.frame is not None:
            for c in ("retrieved_at_utc", "screened_at_utc", "search_result_checked", "roster_date", "scored_at_utc"):
                if c in ds.frame.columns and ds.frame[c].notna().any():
                    retrieved = str(ds.frame[c].dropna().astype(str).max())[:10]
                    break
        prov.append({"Dataset": ds.spec.label, "File": str(ds.path.relative_to(REPO_ROOT)) if ds.path else "",
                     "Data status": STATUS_LABELS[ds.status], "Dated": retrieved,
                     "Notes": ds.spec.description})
    st.dataframe(pd.DataFrame(prov), hide_index=True,
                 column_config={"Notes": st.column_config.TextColumn(width="large")})
