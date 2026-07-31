# syntax=docker/dockerfile:1
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    LEDGERLENS_LLM_ENABLED=false \
    LEDGERLENS_MUTATIONS_ENABLED=false

WORKDIR /app

RUN groupadd --system ledgerlens \
    && useradd --system --gid ledgerlens --home-dir /app ledgerlens

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m pip install --upgrade pip \
    && python -m pip install ".[web,datahub]"

USER ledgerlens

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)" || exit 1

ENTRYPOINT ["ledgerlens"]
CMD ["demo", "--host", "0.0.0.0", "--port", "8000", "--no-open-browser"]
