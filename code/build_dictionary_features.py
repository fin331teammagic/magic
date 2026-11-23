"""Run 2 dictionary features for the Q2 2026 cohort from Capital IQ components.

Computes the five Run 2 variables of ``specs_tried.md`` section 4 locally, with
the Loughran-McDonald 1993-2025 Master Dictionary, from the speaker-tagged
components file (``transcript_components_2024_2026.parquet``) for each
matched call in ``restricted_data/llm_inputs/q2_2026_transcript_match.csv``.

Sections come from the source's own tags, not from parsing speaker labels:

- management prepared remarks: ``Presenter Speech`` by ``Executives``;
- management Q&A: ``Answer`` by ``Executives``;
- analyst questions: ``Question`` by ``Analysts``;
- whole call: every component, in ``componentorder``.

Word tokens, dictionary membership and the sentiment formula
``(positive - negative) / words`` are those of
``code/extract_transcript_features.py``. ``congratulations_mentioned`` follows
the frozen spec: 1 if an analyst question contains "congratulations" or
"congrats" (case-insensitive).

The output holds counts and proportions only, never transcript text. Nothing
is sent anywhere.

    python code/build_dictionary_features.py \\
        --dictionary-csv restricted_data/reference/Loughran-McDonald_MasterDictionary_1993-2025.csv
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_transcript_features import (  # noqa: E402
    DICTIONARY_SOURCE, DICTIONARY_VERSION, _text_metrics, load_dictionary,
)

DEFAULT_MATCH = Path("restricted_data/llm_inputs/q2_2026_transcript_match.csv")
DEFAULT_COMPONENTS = Path("restricted_data/transcript_components_2024_2026.parquet")
DEFAULT_OUT = Path("outputs/q2_2026_dictionary_features.csv")
CONGRATS = re.compile(r"\bcongrat(?:ulations|s)\b", re.IGNORECASE)
COMPONENT_COLUMNS = ["keydevid", "componentorder", "transcriptcomponenttypename",
                     "speakertypename", "componenttext"]
RUN2 = ["transcript_sentiment", "management_prepared_sentiment",
        "analyst_question_sentiment", "uncertainty_word_proportion",
        "congratulations_mentioned"]


def call_features(components, dictionary):
    """Feature row for one call's components (already sorted)."""
    text = components["componenttext"].fillna("").astype(str)
    kind = components["transcriptcomponenttypename"]
    speaker = components["speakertypename"]
    prepared = text[(kind == "Presenter Speech") & (speaker == "Executives")]
    answers = text[(kind == "Answer") & (speaker == "Executives")]
    questions = text[(kind == "Question") & (speaker == "Analysts")]

    whole = _text_metrics(" ".join(text), dictionary)
    prep = _text_metrics(" ".join(prepared), dictionary)
    qa = _text_metrics(" ".join(answers), dictionary)
    analyst = _text_metrics(" ".join(questions), dictionary)
    missing = [name for name, part in
               (("management_prepared", prepared), ("management_qa", answers),
                ("analyst_questions", questions)) if part.str.strip().eq("").all()]
    return {
        "n_components": len(components),
        "transcript_word_count": whole["word_count"],
        "positive_word_proportion": whole["positive_word_proportion"],
        "negative_word_proportion": whole["negative_word_proportion"],
        "uncertainty_word_proportion": whole["uncertainty_word_proportion"],
        "transcript_sentiment": whole["sentiment"],
        "management_prepared_word_count": prep["word_count"],
        "management_prepared_sentiment": prep["sentiment"],
        "management_qa_word_count": qa["word_count"],
        "management_qa_sentiment": qa["sentiment"],
        "analyst_question_word_count": analyst["word_count"],
        "analyst_question_sentiment": analyst["sentiment"],
        "analyst_question_count": len(questions),
        "congratulations_mentioned": (
            int(questions.str.contains(CONGRATS).any()) if len(questions) else None
        ),
        "section_status": "complete" if not missing else ";".join(f"missing_{m}" for m in missing),
    }


def build(match_path, components_path, dictionary_path):
    match = pd.read_csv(match_path)
    matched = match[match["keydevid"].notna()].copy()
    matched["keydevid"] = matched["keydevid"].astype(int)
    keys = set(matched["keydevid"])
    components = pd.read_parquet(components_path, columns=COMPONENT_COLUMNS)
    components = components[components["keydevid"].isin(keys)].copy()
    components["keydevid"] = components["keydevid"].astype(int)
    missing = keys - set(components["keydevid"])
    if missing:
        raise ValueError(f"{len(missing)} matched calls have no components.")
    dictionary = load_dictionary(dictionary_path)
    digest = hashlib.sha256(Path(dictionary_path).read_bytes()).hexdigest()

    rows = []
    for key, part in components.sort_values(["keydevid", "componentorder"]).groupby("keydevid"):
        rows.append({"keydevid": key, **call_features(part, dictionary)})
    features = pd.DataFrame(rows)
    out = matched[["event_id", "ticker", "keydevid", "call_date", "match_status",
                   "after_training_cutoff"]].merge(features, on="keydevid", how="left",
                                                   validate="one_to_one")
    out["dictionary_version"] = DICTIONARY_VERSION
    out["dictionary_source"] = DICTIONARY_SOURCE
    out["dictionary_sha256"] = digest
    out["feature_method"] = "capiq_components_v1"
    out["data_status"] = "cohort"
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--match-csv", type=Path, default=DEFAULT_MATCH)
    parser.add_argument("--components", type=Path, default=DEFAULT_COMPONENTS)
    parser.add_argument("--dictionary-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    out = build(args.match_csv, args.components, args.dictionary_csv)
    if "componenttext" in out.columns or "full_text" in out.columns:
        raise AssertionError("Transcript text must not be written.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    print(f"Wrote {len(out)} calls to {args.output}.")
    print(out["section_status"].value_counts().to_string())
    print(out[RUN2].describe().T.round(4).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
