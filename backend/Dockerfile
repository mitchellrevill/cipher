FROM python:3.12-slim

WORKDIR /app

RUN pip install poetry==1.8.3

COPY pyproject.toml poetry.lock* ./
RUN poetry install --only main --no-root --no-interaction

COPY src/ ./src/
ENV PYTHONPATH=/app/src

EXPOSE 8000
CMD ["poetry", "run", "uvicorn", "redactor.main:app", "--host", "0.0.0.0", "--port", "8000"]
