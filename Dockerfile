# GigaBot Dockerfile
# Build: docker build -t gigabot .
# Run: docker run -p 18790:18790 -v ./config:/root/.nanobot gigabot

# Stage 1: Build Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app
COPY nanobot/ui/dashboard/package.json nanobot/ui/dashboard/package-lock.json ./
RUN npm ci
COPY nanobot/ui/dashboard/ ./
RUN npm run build
# Note: Vite outputs to ./dist by default (configured in vite.config.ts)

# Stage 2: Runtime
FROM python:3.12-slim

# Set environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
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

# Copy built frontend from builder stage to correct location
# Vite is configured to output to '../dist' relative to dashboard dir
# In the builder, WORKDIR is /app and dashboard is copied there, so output is /dist
COPY --from=frontend-builder /dist /app/nanobot/ui/dist

# Install GigaBot with all dependencies
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

# Default: Run legacy gateway (use gateway-v2 for FastAPI)
# To use FastAPI: CMD ["gigabot", "gateway-v2", "--port", "18790"]
CMD ["gigabot", "gateway", "--port", "18790"]
