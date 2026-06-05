FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl pkg-config \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.cargo/bin:${PATH}"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "maturin>=1.7,<2"

COPY pyproject.toml /app/pyproject.toml
COPY native/ /app/native/
COPY src/ /app/src/
RUN maturin build --release --interpreter python3 -o /tmp/wheels \
    && pip install --no-cache-dir /tmp/wheels/*.whl

COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"

CMD ["uvicorn", "pegasus.main:app", "--host", "0.0.0.0", "--port", "8000"]
