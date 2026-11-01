FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    MODEL_ID=distilbert/distilbert-base-uncased-finetuned-sst-2-english \
    MODEL_REVISION=714eb0fa89d2f80546fda750413ed43d93601a13 \
    HF_HOME=/opt/huggingface

WORKDIR /app

# Create a non-root user
RUN useradd --create-home --uid 10001 appuser
RUN mkdir -p /opt/huggingface && chown appuser:appuser /opt/huggingface

# Install dependencies outside the application directory
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# Copy source files with the correct ownership
COPY --chown=appuser:appuser src/ ./src/

USER appuser

# Cache the exact serving model while building, using the runtime user's cache.
RUN python -c 'import os; from transformers import pipeline; pipeline(task="text-classification", model=os.environ["MODEL_ID"], revision=os.environ["MODEL_REVISION"], device=-1)'

# Serving uses the bundled model without contacting Hugging Face.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

EXPOSE 8000

CMD ["uvicorn", "mlops_pipeline.main:app", "--host", "0.0.0.0", "--port", "8000"]
