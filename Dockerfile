FROM python:3.11-slim

ARG INSTALL_LOCAL_MODELS=true
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LITE_RAG_STORAGE_ROOT=/data \
    HF_HOME=/models

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY docker/constraints.txt /app/docker/constraints.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    case "$INSTALL_LOCAL_MODELS" in \
      true) pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu \
            && pip install -c docker/constraints.txt '.[local]' ;; \
      false) pip install -c docker/constraints.txt . ;; \
      *) echo 'INSTALL_LOCAL_MODELS must be true or false' >&2; exit 1 ;; \
    esac

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "lite_rag.api:app", "--host", "0.0.0.0", "--port", "8000"]
