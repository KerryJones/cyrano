FROM python:3.14-slim

WORKDIR /app

# Copy source + config
COPY pyproject.toml .
COPY cyrano/ cyrano/
COPY config/ config/

# Install (non-editable for Docker)
RUN pip install --no-cache-dir .

# Data dir is mounted as a volume at runtime
RUN mkdir -p data

CMD ["python", "-m", "cyrano", "run"]
