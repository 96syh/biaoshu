FROM node:18-bookworm-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
ENV GENERATE_SOURCEMAP=false
RUN npm run build

FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ENABLE_SEARCH_ROUTER=false \
    PORT=8000 \
    HOME=/home/app

WORKDIR /app/backend

COPY backend/requirements.docker.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend/app /app/backend/app
COPY --from=frontend-builder /app/frontend/build /app/backend/static

RUN useradd --create-home --home-dir /home/app --shell /bin/bash app \
    && mkdir -p /app/backend/uploads \
    && chown -R app:app /app /home/app

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
