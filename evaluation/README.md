# Sentiment regression dataset v1

`sentiment-v1.jsonl` contains 24 hand-authored English examples created for this
project: 12 positive and 12 negative. These are synthetic regression cases, not
samples from SST-2 or an independent representative benchmark. They cover clear
sentiment, several domains, and two negation examples. Do not train on these cases.
Dataset changes should create a new version and receive review alongside policy changes.

The initial pinned DistilBERT revision scored accuracy 1.0 and macro F1 1.0 on
2026-10-21. `policy.json` sets both minimums to 0.90, allowing at most two errors
on this balanced dataset (macro F1 is also checked). These are initial regression
tolerances based on that baseline, not production quality targets. Thresholds are
absolute; automatic comparison to the last deployed model is not implemented yet.

The report identifies the exact dataset bytes by SHA-256 and records the resolved
model revision, all predictions, per-class metrics, and the confusion matrix.
Confidence is not used as a substitute for correctness. A failing quality gate
writes its report before exiting with status 1; invalid data or inference errors
also stop the job, but may not produce a report.

Limitations: this small, easy dataset cannot establish generalization, measure
fairness, or demonstrate independence from pretraining data. Add a larger licensed,
held-out dataset, domain-specific cases, and slices before making quality claims.
