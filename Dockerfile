FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for asyncpg and psycopg2
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy all application files
COPY pyproject.toml ./
COPY alembic.ini ./
COPY alembic/ alembic/
COPY src/ src/
COPY scripts/ scripts/
COPY config/ config/

# Install the package
RUN pip install --no-cache-dir -e .

EXPOSE 8000

ENTRYPOINT ["bash", "scripts/start.sh"]
