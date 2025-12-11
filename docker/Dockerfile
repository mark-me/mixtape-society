# docker/Dockerfile  (or just Dockerfile in root)
FROM ghcr.io/astral-sh/uv:0.9.16-python3.13-trixie

# System packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg libtag1-dev gcc libffi-dev libssl-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Now we can copy from the context (project root)
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-cache

# Copy source
COPY src ./src

EXPOSE 5000

ENV FLASK_APP=src/app.py
ENV FLASK_ENV=production

CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:5000", "src.app:app"]