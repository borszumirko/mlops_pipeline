"""Evaluate the real sentiment model and fail closed on quality regressions."""
import argparse
import hashlib
import json
from pathlib import Path

LABELS = ("NEGATIVE", "POSITIVE")


def load_dataset(path):
    raw = Path(path).read_bytes()
    rows = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    if not rows or any(
        not isinstance(row.get("text"), str) or not row["text"].strip()
        or row.get("label") not in LABELS for row in rows
    ):
        raise ValueError("Dataset requires nonempty text and valid sentiment labels")
    if {row["label"] for row in rows} != set(LABELS):
        raise ValueError("Dataset must contain both classes")
    if len({row["text"] for row in rows}) != len(rows):
        raise ValueError("Duplicate dataset texts")
    return rows, hashlib.sha256(raw).hexdigest()


def metrics(expected, predicted):
    if not expected or len(expected) != len(predicted):
        raise ValueError("Predictions must match the nonempty dataset")
    if any(label not in LABELS for label in expected + predicted):
        raise ValueError("Unexpected sentiment label")
    matrix = [[sum(a == x and b == y for a, b in zip(expected, predicted))
               for y in LABELS] for x in LABELS]
    per_class = {}
    for i, label in enumerate(LABELS):
        tp = matrix[i][i]
        support = sum(matrix[i])
        total_predicted = sum(row[i] for row in matrix)
        precision = tp / total_predicted if total_predicted else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = dict(precision=precision, recall=recall, f1=f1, support=support)
    return {
        "accuracy": sum(a == b for a, b in zip(expected, predicted)) / len(expected),
        "macro_f1": sum(v["f1"] for v in per_class.values()) / len(LABELS),
        "per_class": per_class,
        "confusion_matrix": {"labels": LABELS, "rows_actual_columns_predicted": matrix},
    }


def gate(scores, policy):
    return [f"{name} {scores[name]:.4f} below {minimum:.4f}"
            for name, minimum in policy.items() if scores[name] < minimum]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="evaluation/sentiment-v1.jsonl")
    parser.add_argument("--policy", default="evaluation/policy.json")
    parser.add_argument("--output", default="reports/evaluation.json")
    args = parser.parse_args()
    rows, checksum = load_dataset(args.dataset)
    policy = json.loads(Path(args.policy).read_text())
    if set(policy) != {"accuracy", "macro_f1"} or any(
        not isinstance(v, (int, float)) or not 0 <= v <= 1 for v in policy.values()
    ):
        raise ValueError("Policy must define accuracy and macro_f1 thresholds in [0, 1]")
    # Import lazily: metric tests never load ML libraries or weights.
    import torch
    from transformers import pipeline
    from mlops_pipeline.main import MODEL_ID, MODEL_REVISION

    classifier = pipeline("text-classification", model=MODEL_ID,
                          revision=MODEL_REVISION, device=-1)
    with torch.inference_mode():
        results = classifier([row["text"] for row in rows], batch_size=8,
                             truncation=True, max_length=512)
    predicted = [result["label"] for result in results]
    scores = metrics([row["label"] for row in rows], predicted)
    failures = gate(scores, policy)
    report = {
        "model_id": MODEL_ID, "model_revision": classifier.model.config._commit_hash,
        "dataset": str(args.dataset), "dataset_sha256": checksum, "sample_count": len(rows),
        "metrics": scores, "policy": policy, "passed": not failures, "failures": failures,
        "predictions": [dict(row, predicted=label) for row, label in zip(rows, predicted)],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"metrics": scores, "passed": not failures, "failures": failures}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
