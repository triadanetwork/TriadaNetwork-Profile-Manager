FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY worker.py ./worker.py
COPY alembic.ini ./
COPY alembic ./alembic
RUN uv sync --no-dev --extra observability
RUN useradd --create-home --uid 10001 triada
USER triada
ENV TRIADA_CLOUD_HOST=0.0.0.0 TRIADA_CLOUD_PORT=8100 PYTHONUNBUFFERED=1
EXPOSE 8100
HEALTHCHECK --interval=10s --timeout=3s --retries=10 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/health/live', timeout=2).read()"
CMD ["/bin/sh","-c","uv run alembic upgrade head && exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8100 --proxy-headers --forwarded-allow-ips='*'"]
