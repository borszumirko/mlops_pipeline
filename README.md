# Sentiment Analysis API — MLOps & CI/CD

A containerized sentiment analysis REST API built with **FastAPI**, **Hugging Face Transformers**, and **Docker**, with automated testing and CI/CD using **GitHub Actions** and Docker Hub.

## Project Overview

This project demonstrates an end-to-end MLOps workflow for serving a pretrained machine learning model through a REST API. It includes API development, containerization, automated testing, and continuous integration and delivery.

The API uses a pretrained Transformer model to classify text sentiment as **positive** or **negative**.

## Architecture

```text
Client
  |
  v
FastAPI REST API
  |
  v
Hugging Face Sentiment Model
  |
  v
Prediction Response

GitHub Repository
  |
  v
GitHub Actions CI/CD
  |
  +--> Run Automated Tests
  |
  +--> Build Docker Image
  |
  +--> Push Image to Docker Hub
```

## Tech Stack

- **Python** — Application development
- **FastAPI** — REST API framework
- **Hugging Face Transformers** — Pretrained sentiment analysis model
- **PyTorch** — Machine learning inference backend
- **Docker** — Application containerization
- **Pytest** — Automated testing
- **GitHub Actions** — CI/CD automation
- **Docker Hub** — Container image registry

## Features

- REST API for sentiment analysis
- Pretrained Transformer model for text classification
- Health and readiness endpoints
- Input validation
- Automated tests with Pytest
- Dockerized application
- CI/CD pipeline using GitHub Actions
- Automated Docker image builds and publishing
- Versioned Docker images using Git commit SHA tags

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/ready` | Readiness check |
| POST | `/predict` | Predict text sentiment |
| GET | `/docs` | Interactive Swagger API documentation |

### Example Prediction Request

```bash
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{"text": "This project is amazing!"}'
```

### Example Response

```json
{
  "text": "This project is amazing!",
  "sentiment": "POSITIVE",
  "confidence": 0.999
}
```


## CI/CD Pipeline

GitHub Actions automates the testing and container publishing workflow.

The pipeline is designed to:

1. Check out the repository.
2. Set up Python and install dependencies.
3. Run automated tests.
4. Build the Docker image.
5. Authenticate with Docker Hub using GitHub Actions secrets.
6. Push the image to Docker Hub when the configured publishing conditions are met.

### Docker Image Tags

The workflow publishes image tags such as:

- `latest` — The latest published image
- `<commit-sha>` — A version tied to a specific Git commit


## Running Tests

Install the locked dependencies and run the API tests:

```bash
uv sync --locked
uv run pytest -v
```

The tests replace the Hugging Face pipeline factory before application startup,
so they do not download or load model weights. They cover health and readiness,
positive and negative responses, input validation, unavailable models, and
inference failures. These tests verify API behavior; real-model quality evaluation
will be a separate pipeline step.

To explicitly run with Hugging Face offline mode enabled:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest -v
```

## Model Quality Gate

Run real-model evaluation separately from the mocked API tests:

```bash
uv run python -m mlops_pipeline.evaluate
```

The first run downloads model weights. Evaluation and serving use the same pinned
model revision; `MODEL_ID` and `MODEL_REVISION` can override it together.
The evaluator writes `reports/evaluation.json` with accuracy, macro F1, per-class
metrics, a confusion matrix, predictions, and model/dataset identifiers.
It exits with status 1 if accuracy or macro F1 falls below 0.90.

GitHub Actions runs this gate on pull requests and pushes to `main`, uploads the
report even after a quality failure, and requires both tests and evaluation to
pass before publishing an image. Model downloads require access to Hugging Face.

The initial model scored 100% accuracy and macro F1 on the 24 curated examples.
This is a small synthetic regression check, not a real-world benchmark. See
[evaluation documentation](evaluation/README.md) for provenance, policy rationale,
and limitations. Automated deployment and comparison against the deployed model
remain future steps.
