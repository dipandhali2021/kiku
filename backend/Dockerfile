# Kiku API image.
#
# Two stages so the MeCab build toolchain never ships to production. The
# dictionary is baked in at build time: downloading UniDic on container start
# is the classic cause of a 60-second first request on a scale-to-zero host.

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY pyproject.toml ./
COPY app ./app

# Install into a relocatable virtualenv, including the native NLP extras.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install ".[nlp]"

# Verify MeCab actually loaded at build time. Failing here is much better than
# silently degrading to the fallback tokenizer in production.
RUN /opt/venv/bin/python -c "\
import fugashi; t = fugashi.Tagger(); \
assert [w.surface for w in t('日本語を勉強する')]; \
print('MeCab OK')"


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    ENVIRONMENT=production \
    PORT=8080

# Run as a non-root user.
RUN useradd --create-home --uid 10001 kiku

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations

USER kiku
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health').read()"

# Cloud Run and Render both inject $PORT. One worker per container: the
# platform scales by adding containers, and the dictionary is memory-hungry.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
