FROM python:3.11-slim

# Install system dependencies: Redis for job queue, Java for webin-cli jar
RUN apt-get update && apt-get install -y --no-install-recommends \
    redis-server \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Pull uv binary from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy lockfile first so dependency install is cached independently of source changes
COPY pyproject.toml uv.lock ./

# Install into the image's system Python — scripts land in /usr/local/bin with
# correct shebangs, no venv path resolution needed
RUN uv pip install --system --no-cache-dir \
    "ipykernel>=7.1.0" \
    "pandas>=2.3.2" \
    "polars>=1.33.1" \
    "redis>=7.4.0" \
    "rq>=2.9.0" \
    "streamlit>=1.49.1" \
    "streamlit-option-menu>=0.4.0" \
    "tqdm>=4.67.1"

# Copy project source
COPY . .

RUN chmod +x start.sh

EXPOSE 8501

CMD ["/app/start.sh"]
