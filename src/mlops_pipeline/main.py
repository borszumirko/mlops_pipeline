import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_ID = os.getenv(
    "MODEL_ID",
    "distilbert/distilbert-base-uncased-finetuned-sst-2-english",
)

MODEL_REVISION = os.getenv(
    "MODEL_REVISION", "714eb0fa89d2f80546fda750413ed43d93601a13"
)

MAX_TEXT_LENGTH = 5000


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load the classifier on startup and log application shutdown."""
    logger.info("Loading sentiment model: %s", MODEL_ID)

    app.state.classifier = pipeline(
        task="text-classification",
        model=MODEL_ID,
        revision=MODEL_REVISION,
        device=-1,
    )

    logger.info("Sentiment model loaded successfully")

    yield

    logger.info("Shutting down sentiment API")


app = FastAPI(
    title="Sentiment Analysis API",
    description="Sentiment classification using a Hugging Face model.",
    version="1.0.0",
    lifespan=lifespan,
)


class SentimentRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=MAX_TEXT_LENGTH,
        description="English text to classify.",
    )


class SentimentResponse(BaseModel):
    text: str
    sentiment: str
    confidence: float


@app.get("/health")
def health_check() -> dict[str, str]:
    """Return process health independently of model availability."""
    return {"status": "healthy"}


@app.get("/ready")
def readiness_check() -> dict[str, str]:
    """Return model readiness, raising HTTP 503 while unavailable."""
    classifier = getattr(app.state, "classifier", None)

    if classifier is None:
        raise HTTPException(
            status_code=503,
            detail="Model is not ready",
        )

    return {
        "status": "ready",
        "model": MODEL_ID,
    }


@app.post(
    "/predict",
    response_model=SentimentResponse,
)
def predict(request: SentimentRequest) -> SentimentResponse:
    """Classify trimmed text, rejecting blank input or unavailable inference.

    Raises:
        HTTPException: For blank text (422), an unavailable model (503),
            or a failed prediction (500).
    """
    text = request.text.strip()

    if not text:
        raise HTTPException(
            status_code=422,
            detail="Text must not be empty or whitespace only.",
        )

    classifier = getattr(app.state, "classifier", None)

    if classifier is None:
        raise HTTPException(
            status_code=503,
            detail="Model is not ready",
        )

    try:
        with torch.inference_mode():
            result = classifier(
                text,
                truncation=True,
                max_length=512,
            )[0]

        return SentimentResponse(
            text=text,
            sentiment=result["label"],
            confidence=round(float(result["score"]), 6),
        )

    except Exception:
        logger.exception("Sentiment prediction failed")

        raise HTTPException(
            status_code=500,
            detail="Prediction failed",
        )
