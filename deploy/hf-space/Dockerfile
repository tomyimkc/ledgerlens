FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system ledgerlens \
    && useradd --system --gid ledgerlens --home-dir /app ledgerlens

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY app.py ./app.py

RUN python -m pip install --upgrade pip \
    && python -m pip install ".[web]"

USER ledgerlens
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/healthz', timeout=3)" || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--no-access-log"]

