FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Build context is the repo root so data/ and docs/queries.cypher are in the image.
COPY services/api/pyproject.toml ./
COPY services/api/app ./app
COPY data ./data
COPY docs/queries.cypher ./docs/queries.cypher

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
