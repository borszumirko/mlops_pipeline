FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    MODEL_ID=distilbert/distilbert-base-uncased-finetuned-sst-2-english

WORKDIR /app

# Create a non-root user
RUN useradd --create-home --uid 10001 appuser

# Install dependencies outside the application directory
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# Copy source files with the correct ownership
COPY --chown=appuser:appuser src/ ./src/

USER appuser

EXPOSE 8000

CMD ["uvicorn", "mlops_pipeline.main:app", "--host", "0.0.0.0", "--port", "8000"]