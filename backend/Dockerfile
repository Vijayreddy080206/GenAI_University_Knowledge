# ==============================================================================
# NIIT University - Generative AI-Based University Knowledge Assistant
# Production Multi-Stage Dockerfile (REQ-OPS-01, SDD Section 5.5)
# Capstone Project II - Team-20 (Supervised by Prof. Manish Hurkat)
# ==============================================================================

FROM python:3.11-slim as builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final Lean Runtime Stage
FROM python:3.11-slim as runner

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Security: Non-root user execution
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/storage/documents && \
    chown -R appuser:appuser /app

COPY --chown=appuser:appuser . /app

USER appuser

EXPOSE 8000

# Healthcheck probe matching REQ-OPS-03
HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
