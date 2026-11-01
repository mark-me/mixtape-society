# syntax=docker/dockerfile:1

# Every stage runs on the same Python image: the virtual environment made in the build stage
# only works with the Python it was made for. The image appears in each FROM below, so
# Dependabot moves them together. A new Python version comes with .python-version.
#
# uv comes from its own image, at a fixed version.
FROM ghcr.io/astral-sh/uv:0.13.1 AS uv


# Build stage: install the locked dependencies, without the development tools.
FROM python:3.13-slim-trixie AS build

COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first, so this layer is reused while only the source changes.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-cache --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-cache --no-dev


# Runtime stage: Python, the virtual environment, the source, and what the app calls on.
FROM python:3.13-slim-trixie

# ffmpeg transcodes the audio; CairoSVG needs the Cairo library.
# Upgraded as well: the base image can lag behind Debian's security fixes.
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends ffmpeg libcairo2 && \
    rm -rf /var/lib/apt/lists/*

# pip is not needed to run the app, and what it carries along would only be found by the scan.
RUN python -m pip uninstall --yes pip

WORKDIR /app

# Build argument for version
ARG APP_VERSION=dev

RUN mkdir /music

COPY --from=build /app/.venv /app/.venv
COPY src ./src

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION}

# The build fails here, not the container at its start, when the environment does not fit.
RUN python -c "import src.app, gunicorn"

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--log-level", "info", "src.app:create_app()"]
