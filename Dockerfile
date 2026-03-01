# Multi-stage build: builder installs deps, runtime keeps minimal surface
# --- Builder ---
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --no-warn-script-location -r requirements.txt

# --- Runtime ---
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV PYTHONPATH=/app

# Non-root user for container process
RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --shell /bin/sh --create-home app

WORKDIR /app

# Copy installed packages from builder (no build tools in final image)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Application code
COPY --chown=app:app . .

USER app

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
