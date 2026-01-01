# docker/Dockerfile
FROM ghcr.io/astral-sh/uv:0.9.16-python3.13-trixie

# System packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg libtag1-dev gcc libffi-dev libssl-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Declare ARG after FROM so it's available, and move ENV to AFTER we have the files
ARG APP_VERSION=dev

RUN mkdir /music

# Copy from project root
COPY pyproject.toml uv.lock ./
COPY src ./src

# Install dependencies
RUN uv sync --frozen --no-cache

EXPOSE 5000

ENV PYTHONPATH=/app/src

ENV APP_VERSION=${APP_VERSION}

CMD ["uv", "run", "-m", "gunicorn", "--bind", "0.0.0.0:5000", "--log-level", "info", "src.app:create_app()"]
