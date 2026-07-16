# syntax=docker/dockerfile:1.7

# The amd64 release image keeps the locked local Paddle OCR rollback runtime.
# Linux/arm64 is a native development image because PaddlePaddle 3.3.1 has no
# compatible Linux wheel; API, migrations and NewAPI image analysis still run.
FROM python:3.12-slim AS model-builder

WORKDIR /build
COPY src/study_api/model_provisioning.py src/study_api/model_provisioning.py
COPY scripts/provision_models.py scripts/provision_models.py
COPY ocr-model-manifest.json ocr-model-manifest.json
RUN architecture="$(dpkg --print-architecture)"; \
    if [ "${architecture}" = "amd64" ]; then \
        PYTHONPATH=/build/src python scripts/provision_models.py \
            --manifest /build/ocr-model-manifest.json \
            --output /opt/study/models; \
    elif [ "${architecture}" = "arm64" ]; then \
        mkdir -p /opt/study/models; \
    else \
        echo "Unsupported target architecture: ${architecture}" >&2; \
        exit 1; \
    fi

FROM ghcr.io/astral-sh/uv:0.8.15-python3.12-bookworm-slim AS dependencies

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

FROM python:3.12-slim AS runtime

WORKDIR /app
RUN architecture="$(dpkg --print-architecture)"; \
    if [ "${architecture}" = "amd64" ]; then \
        apt-get update; \
        apt-get install --no-install-recommends -y libgl1 libglib2.0-0 libgomp1; \
        rm -rf /var/lib/apt/lists/*; \
    elif [ "${architecture}" != "arm64" ]; then \
        echo "Unsupported target architecture: ${architecture}" >&2; \
        exit 1; \
    fi
COPY --from=dependencies /app/.venv /app/.venv
COPY --from=model-builder /opt/study/models /opt/study/models
COPY src ./src
COPY migrations ./migrations
COPY scripts ./scripts
COPY alembic.ini ./alembic.ini

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/src" \
    PADDLE_MODEL_ROOT="/opt/study/models" \
    STUDY_OCR_CONTAINER_RUNTIME="true" \
    PYTHONUNBUFFERED="1"

EXPOSE 8000
CMD ["uvicorn", "study_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
