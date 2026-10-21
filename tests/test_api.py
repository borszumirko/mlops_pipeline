from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

import mlops_pipeline.main as api


class FakeClassifier:
    def __call__(self, text, **kwargs):
        if "terrible" in text.lower():
            return [{"label": "NEGATIVE", "score": 0.98}]
        return [{"label": "POSITIVE", "score": 0.97}]


@pytest.fixture
def client(monkeypatch):
    # Replace the factory before startup to prevent model downloads and loading.
    factory = Mock(return_value=FakeClassifier())
    monkeypatch.setattr(api, "pipeline", factory)
    # Restore state after each test, including tests that remove the classifier.
    monkeypatch.setattr(api.app.state, "classifier", None, raising=False)
    with TestClient(api.app) as test_client:
        factory.assert_called_once_with(
            task="text-classification", model=api.MODEL_ID,
            revision=api.MODEL_REVISION, device=-1
        )
        yield test_client


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_ready_endpoint(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "model": api.MODEL_ID}


@pytest.mark.parametrize(
    ("text", "sentiment", "confidence"),
    [
        ("  I love this product!  ", "POSITIVE", 0.97),
        ("This was terrible.", "NEGATIVE", 0.98),
    ],
)
def test_prediction(client, text, sentiment, confidence):
    response = client.post("/predict", json={"text": text})
    assert response.status_code == 200
    assert response.json() == {
        "text": text.strip(),
        "sentiment": sentiment,
        "confidence": confidence,
    }


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"text": ""},
        {"text": "   "},
        {"text": "x" * (api.MAX_TEXT_LENGTH + 1)},
        {"text": None},
        {"text": 123},
        {"text": ["hello"]},
    ],
)
def test_invalid_input_is_rejected(client, payload):
    response = client.post("/predict", json=payload)
    assert response.status_code == 422


@pytest.mark.parametrize("missing_attribute", [False, True])
def test_model_unavailable(client, monkeypatch, missing_attribute):
    if missing_attribute:
        monkeypatch.delattr(api.app.state, "classifier")
    else:
        monkeypatch.setattr(api.app.state, "classifier", None)
    assert client.get("/health").status_code == 200
    for response in (
        client.get("/ready"),
        client.post("/predict", json={"text": "hello"}),
    ):
        assert response.status_code == 503
        assert response.json() == {"detail": "Model is not ready"}


def test_inference_failure(client, monkeypatch):
    classifier = Mock(side_effect=RuntimeError("internal model failure"))
    monkeypatch.setattr(api.app.state, "classifier", classifier)
    response = client.post("/predict", json={"text": "hello"})
    assert response.status_code == 500
    assert response.json() == {"detail": "Prediction failed"}
