FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer cache)
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy source
COPY cyrano/ cyrano/
COPY config/ config/

# Data dir is mounted as a volume at runtime
RUN mkdir -p data

CMD ["python", "-m", "cyrano", "run"]
