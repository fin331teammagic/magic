"""Read the exploratory LLM-question screens for the dashboard.

Presentation only. ``code/explore_llm_questions.py`` writes one folder per
screen under ``outputs/exploratory_llm_questions/`` (for example
``v2.0_gemma4``); this module lists and loads those folders and applies the
team's *proposed* lead rule to rows that are already computed. Nothing here
estimates anything.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / "outputs" / "exploratory_llm_questions"
FILES = ("one_at_a_time", "distribution", "agreement", "overlap", "block", "sample_flow", "score_files")
REQUIRED = "one_at_a_time"
CONSENSUS = "consensus"

# Proposed in the team message of 2026-11-24, not yet agreed. Change here.
LEAD_Q_MAX = 0.05
LEAD_PLACEBO_MAX = 0.10
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
    """One row per model and question (nulls dropped), with the proposed lead checks.

    - ``same_direction``: the coefficient has the same sign for at least
      ``LEAD_MIN_MODELS`` real models (the consensus row is not counted). With
      fewer real models than that, it cannot be checked and is False.
    - ``survives_multiple_testing``: BH q within the model below ``LEAD_Q_MAX``.
    - ``helps_holdout``: holdout MSE gain above 0 and placebo share below
      ``LEAD_PLACEBO_MAX``.
    - ``proposed_lead``: all three.
    """
    rows = single[single["null_handling"] == "dropped"].copy()
    for column in ("coef", "bh_q_within_model", "delta_mse", "placebo_share"):
        if column not in rows:
            rows[column] = float("nan")
    real = rows[rows["model"] != CONSENSUS]
    n_models = real["model"].nunique()
    signs = real.assign(sign=real["coef"].apply(lambda c: (c > 0) - (c < 0) if pd.notna(c) else 0))
    agreeing = signs.groupby("variable")["sign"].agg(lambda s: max((s > 0).sum(), (s < 0).sum()))
    rows["models_same_direction"] = rows["variable"].map(agreeing).fillna(0).astype(int)
    rows["n_models"] = n_models
    rows["same_direction"] = (n_models >= LEAD_MIN_MODELS) & (rows["models_same_direction"] >= LEAD_MIN_MODELS)
    rows["survives_multiple_testing"] = rows["bh_q_within_model"] < LEAD_Q_MAX
    rows["helps_holdout"] = (rows["delta_mse"] > 0) & (rows["placebo_share"] < LEAD_PLACEBO_MAX)
    rows["proposed_lead"] = rows["same_direction"] & rows["survives_multiple_testing"] & rows["helps_holdout"]
    return rows.sort_values(["proposed_lead", "bh_q_within_model"], ascending=[False, True])
