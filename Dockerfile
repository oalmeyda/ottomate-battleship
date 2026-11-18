FROM python:3.15-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY wheels ./wheels
RUN pip install --no-cache-dir ./wheels/*.whl

COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir . && \
    python -m compileall -q /usr/local/lib/python3.15/site-packages /app/app

USER 10001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
