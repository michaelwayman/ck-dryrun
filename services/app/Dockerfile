# syntax=docker/dockerfile:1
# Build context: the repo root, because the uv workspace lock and libs/ live there.
# Targets: `runtime` (gunicorn, what compose runs) and `dev` (whole workspace with the dev tools).

FROM ghcr.io/astral-sh/uv:0.13.5 AS uv

# <BrandList /> bundle and compiled SCSS, gathered in /out in the layout Django static expects.
FROM node:26-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/ ./
# build:css skips itself until frontend/scss/main.scss exists (M7), so css/ is optional.
RUN npm run build && npm run build:css \
    && mkdir /out \
    && if [ -d dist/css ]; then mv dist/css /out/css; fi \
    && mv dist /out/brandlist

FROM python:3.14-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
RUN useradd --uid 1000 --user-group --no-create-home --shell /usr/sbin/nologin app

FROM base AS uv-base
COPY --from=uv /uv /uvx /bin/
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /workspace

# Third-party deps first, from the lock and the members' pyproject files only, so this layer
# survives source edits. --locked needs every member's pyproject.toml to check the lock.
FROM uv-base AS builder
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=services/app/pyproject.toml,target=services/app/pyproject.toml \
    --mount=type=bind,source=services/auth/pyproject.toml,target=services/auth/pyproject.toml \
    --mount=type=bind,source=libs/tokenauth/pyproject.toml,target=libs/tokenauth/pyproject.toml \
    uv sync --locked --no-dev --no-install-workspace --package app
COPY pyproject.toml uv.lock ./
COPY libs/ libs/
COPY services/auth/pyproject.toml services/auth/
COPY services/app/ services/app/
# Non-editable, so tokenauth lands in the venv and the runtime image needs no libs/ source.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable --package app

FROM base AS runtime
ENV PYTHONDONTWRITEBYTECODE=1
COPY --from=builder /opt/venv /opt/venv
COPY services/app/ /srv/app/
COPY --from=frontend /out/ /srv/app/static/
WORKDIR /srv/app
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--access-logfile", "-"]

# ruff, mypy and pytest for every workspace member; #4's make targets run here.
FROM uv-base AS dev
# Settings refuse to load without a secret key unless debug is on; mypy's Django plugin loads them.
ENV DJANGO_DEBUG=true
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=services/app/pyproject.toml,target=services/app/pyproject.toml \
    --mount=type=bind,source=services/auth/pyproject.toml,target=services/auth/pyproject.toml \
    --mount=type=bind,source=libs/tokenauth/pyproject.toml,target=libs/tokenauth/pyproject.toml \
    uv sync --locked --all-packages --all-groups --all-extras --no-install-workspace
# The tools write caches (.ruff_cache, .mypy_cache, .pytest_cache) into the workspace.
RUN chown app:app /workspace
COPY --chown=app:app pyproject.toml uv.lock ./
COPY --chown=app:app libs/ libs/
COPY --chown=app:app services/ services/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --all-packages --all-groups --all-extras
WORKDIR /workspace/services/app
USER app
