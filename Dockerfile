FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e . 2>/dev/null || pip install --no-cache-dir .

# Copy source code
COPY echa_mcp/ ./echa_mcp/

# Expose SSE port
EXPOSE 8005

# Health check — SSE endpoint responds to GET
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8005/sse || exit 1

# Run server
CMD ["python", "-m", "echa_mcp.server"]
