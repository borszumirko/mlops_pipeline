from fastapi.testclient import TestClient
from mlops_pipeline.main import app


# fake classifier so test are fast
class FakeClassifier:
    def __call__(self, text, **kwargs):
        if "terrible" in text.lower():
            return [{"label": "NEGATIVE", "score": 0.98}]

        return [{"label": "POSITIVE", "score": 0.97}]


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_ready_endpoint():
    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_positive_prediction(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setattr(
            app.state,
            "classifier",
            FakeClassifier(),
        )

        response = client.post(
            "/predict",
            json={"text": "I love this product!"},
        )

    assert response.status_code == 200

    body = response.json()

    assert body["sentiment"] == "POSITIVE"
    assert body["confidence"] == 0.97
    assert body["text"] == "I love this product!"


def test_negative_prediction(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setattr(
            app.state,
            "classifier",
            FakeClassifier(),
        )

        response = client.post(
            "/predict",
            json={"text": "This was terrible."},
        )

    assert response.status_code == 200
    assert response.json()["sentiment"] == "NEGATIVE"


def test_empty_text_is_rejected():
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json={"text": "   "},
        )

    assert response.status_code == 422


def test_missing_text_is_rejected():
    with TestClient(app) as client:
        response = client.post("/predict", json={})

    assert response.status_code == 422
