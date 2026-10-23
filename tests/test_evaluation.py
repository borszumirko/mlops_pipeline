import json
from pathlib import Path

import pytest

from mlops_pipeline.evaluate import gate, load_dataset, metrics


def test_confusion_matrix_and_macro_f1() -> None:
    """Verify aggregate metrics and confusion counts for mixed predictions."""
    scores = metrics(
        ["NEGATIVE", "NEGATIVE", "POSITIVE", "POSITIVE"],
        ["NEGATIVE", "POSITIVE", "POSITIVE", "POSITIVE"],
    )
    assert scores["accuracy"] == 0.75
    assert scores["macro_f1"] == pytest.approx((2 / 3 + 0.8) / 2)
    assert scores["confusion_matrix"]["rows_actual_columns_predicted"] == [[1, 1], [0, 2]]


def test_single_class_collapse_fails_gate() -> None:
    """Verify predicting only one class fails the quality thresholds."""
    scores = metrics(["NEGATIVE", "POSITIVE"], ["POSITIVE", "POSITIVE"])
    assert scores["per_class"]["NEGATIVE"]["f1"] == 0
    assert len(gate(scores, {"accuracy": 0.9, "macro_f1": 0.9})) == 2


def test_gate_accepts_exact_threshold() -> None:
    """Verify scores equal to a threshold pass the gate."""
    assert gate({"accuracy": 0.9}, {"accuracy": 0.9}) == []


@pytest.mark.parametrize("predicted", [[], ["UNKNOWN"], ["POSITIVE", "NEGATIVE"]])
def test_invalid_predictions_fail_closed(predicted: list[str]) -> None:
    """Verify empty, unknown, or mismatched predictions are rejected."""
    with pytest.raises(ValueError):
        metrics(["POSITIVE"], predicted)


@pytest.mark.parametrize("rows", [[], [{"text": "hello", "label": "POSITIVE"}],
    [{"text": "", "label": "NEGATIVE"}],
    [{"text": "same", "label": "NEGATIVE"}, {"text": "same", "label": "POSITIVE"}]])
def test_invalid_dataset(tmp_path: Path, rows: list[dict[str, str]]) -> None:
    """Verify invalid or incomplete evaluation datasets are rejected."""
    path = tmp_path / "data.jsonl"
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    with pytest.raises(ValueError):
        load_dataset(path)


def test_versioned_dataset() -> None:
    """Verify the versioned dataset sample count and digest length."""
    rows, checksum = load_dataset("evaluation/sentiment-v1.jsonl")
    assert len(rows) == 24
    assert len(checksum) == 64
