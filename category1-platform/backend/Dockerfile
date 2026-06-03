FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    unixodbc-dev gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY category1/ category1/

ENV CATEGORY1_WORK_DIR=/data/category1
RUN mkdir -p /data/category1

EXPOSE 8000

CMD ["uvicorn", "category1.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
