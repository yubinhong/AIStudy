# syntax=docker/dockerfile:1.7

# paddlepaddle==3.3.1 has no Linux arm64 wheel; Ubuntu deployment and Docker
# builds therefore target Linux x86_64. Docker Desktop can emulate this on arm64.
FROM --platform=linux/amd64 python:3.12-slim AS model-builder

WORKDIR /build
COPY src/study_api/model_provisioning.py src/study_api/model_provisioning.py
COPY scripts/provision_models.py scripts/provision_models.py
COPY ocr-model-manifest.json ocr-model-manifest.json
RUN PYTHONPATH=/build/src python scripts/provision_models.py \
    --manifest /build/ocr-model-manifest.json \
    --output /opt/study/models

FROM --platform=linux/amd64 ghcr.io/astral-sh/uv:0.8.15-python3.12-bookworm-slim AS dependencies

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

FROM --platform=linux/amd64 python:3.12-slim AS runtime

WORKDIR /app
RUN apt-get update \
    && apt-get install --no-install-recommends -y libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=dependencies /app/.venv /app/.venv
COPY --from=model-builder /opt/study/models /opt/study/models
COPY src ./src

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/src" \
    PADDLE_MODEL_ROOT="/opt/study/models" \
    PYTHONUNBUFFERED="1"

EXPOSE 8000
CMD ["uvicorn", "study_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
