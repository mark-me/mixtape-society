# docker/Dockerfile  (or just Dockerfile in root)
FROM ghcr.io/astral-sh/uv:0.9.16-python3.13-trixie

# System packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg libtag1-dev gcc libffi-dev libssl-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN mkdir /music

# Now we can copy from the context (project root)
COPY pyproject.toml uv.lock ./

# Copy source
COPY src ./src

# Install dependencies
RUN uv sync --frozen --no-cache

EXPOSE 5000

ENV PYTHONPATH=/app/src

CMD ["uv", "run", "-m", "gunicorn", "--bind", "0.0.0.0:5000", "--log-level", "info", "src.app:app"]