"""Read the exploratory LLM-question screens for the dashboard.

Presentation only. ``code/explore_llm_questions.py`` writes one folder per
screen under ``outputs/exploratory_llm_questions/`` (for example
``v2.0_gemma4``); this module lists and loads those folders and applies the
team's lead rule (``specs_tried.md`` Amendment 6) to rows that are already computed. Nothing here
estimates anything.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / "outputs" / "exploratory_llm_questions"
FILES = ("one_at_a_time", "distribution", "agreement", "overlap", "block", "sample_flow", "score_files")
REQUIRED = "one_at_a_time"
CONSENSUS = "consensus"

# Fixed 2026-11-24 (Abby, Michelle) before any v3.0 score was received;
# recorded in specs_tried.md Amendment 6. Change only by a new amendment.
LEAD_Q_MAX = 0.10
LEAD_PLACEBO_MAX = 0.05
LEAD_MIN_MODELS = 2


def list_screens(root: Path = ROOT) -> list[str]:
    """Screen folders that contain at least the one-at-a-time file, newest name last."""
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir() if (p / f"{REQUIRED}.csv").exists())


def load_screen(name: str, root: Path = ROOT) -> dict[str, pd.DataFrame | None]:
    """Every output file of one screen; a missing or unreadable file is None."""
    frames = {}
    for key in FILES:
        try:
            frames[key] = pd.read_csv(root / name / f"{key}.csv")
        except Exception:  # absent or malformed: the tab says so instead of crashing
            frames[key] = None
    return frames


def proposed_leads(single: pd.DataFrame) -> pd.DataFrame:
    """One row per model and question (nulls dropped), with the Amendment 6 lead checks.

    - ``survives_multiple_testing``: BH q within the model below ``LEAD_Q_MAX``.
    - ``helps_holdout``: holdout MSE gain above 0 and placebo share below
      ``LEAD_PLACEBO_MAX``.
    - ``passes_alone``: both of the above, for this model.
    - ``models_passing_same_sign``: real models (the consensus row is not
      counted) that pass alone with the same coefficient sign as this row.
    - ``replicates``: at least ``LEAD_MIN_MODELS`` such models. With fewer
      real models than that, it cannot pass.
    - ``proposed_lead``: passes alone and replicates.

    Requiring the *checks* to replicate, not just the sign, matters: with
    three models at least two always share a sign, so a sign-only rule
    passed a chance result in a rehearsal on random scores.
    """
    rows = single[single["null_handling"] == "dropped"].copy()
    for column in ("coef", "bh_q_within_model", "delta_mse", "placebo_share"):
        if column not in rows:
            rows[column] = float("nan")
    rows["survives_multiple_testing"] = rows["bh_q_within_model"] < LEAD_Q_MAX
    rows["helps_holdout"] = (rows["delta_mse"] > 0) & (rows["placebo_share"] < LEAD_PLACEBO_MAX)
    rows["passes_alone"] = rows["survives_multiple_testing"] & rows["helps_holdout"]
    rows["sign"] = rows["coef"].apply(lambda c: (c > 0) - (c < 0) if pd.notna(c) else 0)
    passing = rows[(rows["model"] != CONSENSUS) & rows["passes_alone"] & (rows["sign"] != 0)]
    counts = passing.groupby(["variable", "sign"]).size()
    rows["models_passing_same_sign"] = [
        int(counts.get((v, sg), 0)) for v, sg in zip(rows["variable"], rows["sign"])]
    rows["n_models"] = rows.loc[rows["model"] != CONSENSUS, "model"].nunique()
    rows["replicates"] = rows["models_passing_same_sign"] >= LEAD_MIN_MODELS
    rows["proposed_lead"] = rows["passes_alone"] & rows["replicates"]
    return rows.drop(columns="sign").sort_values(["proposed_lead", "bh_q_within_model"],
                                                 ascending=[False, True])
