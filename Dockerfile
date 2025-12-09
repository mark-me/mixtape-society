# ================================
# Mixtape Society – Dockerfile
# ================================

# Official uv-image (bevat al uv + pip + Python)
FROM ghcr.io/astral-sh/uv:0.9.16-python3.11-trixie

WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./
COPY uv.lock ./

# Install python dependencies
RUN uv sync --frozen --no-cache

# Copy source code
COPY src ./src

# Install system packages for audio/metadata (ffmpeg + libtag)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libtag1-dev \
        gcc \
        libffi-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 5000

# Ser environment
ENV FLASK_APP=src/app.py
ENV FLASK_ENV=production

# Start commando
CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:5000", "src.app:app"]