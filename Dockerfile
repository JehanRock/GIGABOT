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
COPY bridge/ bridge/

# Install GigaBot
RUN pip install --no-cache-dir .

# Install optional dependencies for full functionality
RUN pip install --no-cache-dir aiohttp numpy tiktoken

# Create config and workspace directories
RUN mkdir -p /root/.nanobot/workspace /root/.nanobot/memory

# Expose ports
# 18790: HTTP/WebSocket API (Dashboard, Chat, Nodes)
EXPOSE 18790

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:18790/health || exit 1

# Run GigaBot gateway (both gigabot and nanobot commands work)
CMD ["gigabot", "gateway", "--port", "18790"]
