FROM python:3.13-slim

# Install system dependencies and create non-root user in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 api \
    && useradd --uid 1000 --gid api --shell /bin/bash --create-home api

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.8.13 /uv /uvx /usr/local/bin/

# Set working directory and change ownership
WORKDIR /code
RUN chown -R api:api /code

# Switch to non-root user
USER api

# Set uv environment variables
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/code/.venv \
    PYTHONPATH=/code:/code/common \
    LOG_LEVEL=INFO

# Copy dependency files and install dependencies
COPY --chown=api:api uv.lock pyproject.toml ./

# Install dependencies using mount cache
RUN --mount=type=cache,target=/home/api/.cache/uv,uid=1000,gid=1000 \
    uv sync --locked --no-dev

# Copy application code
COPY --chown=api:api api ./api
COPY --chown=api:api common ./common
COPY --chown=api:api logging.yaml ./

ENTRYPOINT ["uv", "run", "--locked"]
# Use exec form and combine ENTRYPOINT and CMD properly
CMD ["uvicorn", "api.main:app", \
     "--log-config", "./logging.yaml", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--no-access-log", \
     "--timeout-keep-alive", "60"]
