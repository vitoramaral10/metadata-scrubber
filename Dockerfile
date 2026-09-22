# syntax=docker/dockerfile:1

# Base fixada por digest: tag e movel, e build reproduzivel importa no dia do
# post-mortem. Renovate/Dependabot atualizam o digest.
ARG PYTHON_IMAGE=python:3.13-slim@sha256:8d9d0b8bcf6506481eae4907c18f5e3e7902e629f5f6d684f9e7c32e85e3ddf0

FROM ghcr.io/astral-sh/uv:0.9-python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /srv/metadata-scrubber

# Manifestos primeiro: a camada cara de dependencia so invalida quando elas mudam.
COPY pyproject.toml README.md ./
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /srv/metadata-scrubber/.venv \
 && uv pip install --python /srv/metadata-scrubber/.venv --no-editable .

FROM ${PYTHON_IMAGE} AS runtime

ENV PATH="/srv/metadata-scrubber/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GRADIO_ANALYTICS_ENABLED=False \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860 \
    SCRUBBER_WORK_DIR=/tmp/metadata-scrubber \
    HOME=/tmp \
    MPLCONFIGDIR=/tmp

# Arquivos da aplicacao pertencem a root e sao somente leitura para o processo:
# bug de escrita de arquivo nao vira execucao de codigo persistente.
COPY --from=builder --chown=root:root --chmod=755 /srv/metadata-scrubber/.venv /srv/metadata-scrubber/.venv

WORKDIR /srv/metadata-scrubber
USER 65532:65532
EXPOSE 7860

ENTRYPOINT ["/srv/metadata-scrubber/.venv/bin/metadata-scrubber-web"]
