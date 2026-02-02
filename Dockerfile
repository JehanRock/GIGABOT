# GigaBot Dockerfile
# Build: docker build -t gigabot .
# Run: docker run -p 18790:18790 -v ./config:/root/.nanobot gigabot

FROM python:3.11-slim

# Set environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOME=/root

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY nanobot/ nanobot/

# Install GigaBot
RUN pip install --no-cache-dir -e .

# Install optional dependencies
RUN pip install --no-cache-dir aiohttp numpy

# Create config directory
RUN mkdir -p /root/.nanobot/workspace

# Expose ports
# 18790: HTTP/WebSocket API
# 18791: Alternative port (not used by default)
EXPOSE 18790 18791

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:18790/health || exit 1

# Run GigaBot
CMD ["nanobot", "gateway"]
