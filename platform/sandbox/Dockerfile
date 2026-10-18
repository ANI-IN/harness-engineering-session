# shipharness sandbox images. Build from the repository root:
#   docker build -f platform/sandbox/Dockerfile --target agent   -t shipharness-agent:1 .
#   docker build -f platform/sandbox/Dockerfile --target referee -t shipharness-referee:1 .
# Dependencies are baked in at build time; containers run with --network none.
# .dockerignore keeps .env and other local state out of the build context: no key enters an image.

FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /opt/build
COPY pyproject.toml uv.lock ./
# [walkthrough:S3:dockerfile] start
# Bytecode is compiled at build time: PYTHONDONTWRITEBYTECODE keeps containers from writing it, so
# without this every Python process in a container compiled every imported module from source
# again (about 3 s per pytest start). Bytecode comes from the same source: results do not change.
RUN UV_COMPILE_BYTECODE=1 uv sync --frozen --no-install-project --group dev
# Non-root user; the workspace is bind-mounted at /work and is the only writable path besides /tmp.
RUN useradd --uid 1000 --create-home agent \
    && git config --system user.name "agent" \
    && git config --system user.email "agent@sandbox.invalid" \
    && git config --system --add safe.directory /work
# The check runner (python -m shipharness.checks.runner) comes from the image, never the workspace.
COPY platform/src/ /opt/shipharness/src/
# The slim base image ships its standard library without bytecode: compile it, and the checks.
RUN python -m compileall -q /usr/local/lib/python3.12 /opt/shipharness/src
ENV PYTHONPATH=/opt/shipharness/src

FROM base AS agent
USER 1000:1000
WORKDIR /work
# [walkthrough:S3:dockerfile] end

FROM base AS referee
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright
RUN playwright install --with-deps chromium && chmod -R a+rX /opt/ms-playwright
USER 1000:1000
WORKDIR /work
