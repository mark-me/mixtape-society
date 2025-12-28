# docker/Dockerfile  (or just Dockerfile in root)
FROM ghcr.io/astral-sh/uv:0.9.16-python3.13-trixie

# System packages including FFmpeg for FLAC→MP3 conversion
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libtag1-dev \
        gcc \
        libffi-dev \
        libssl-dev && \
    rm -rf /var/lib/apt/lists/*

# Verify FFmpeg installation
RUN ffmpeg -version

WORKDIR /app

ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION

RUN mkdir /music

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Copy source
COPY src ./src

# Install dependencies
RUN uv sync --frozen --no-cache

EXPOSE 5000

ENV PYTHONPATH=/app/src

CMD ["uv", "run", "-m", "gunicorn", "--bind", "0.0.0.0:5000", "--log-level", "info", "src.app:create_app()"]
