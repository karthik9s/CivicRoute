# CivicRoute - single container: React build served by the FastAPI app.
#   docker compose --profile app up -d --build      (app + pgvector)
# Secrets are NOT baked in: pass them at runtime via backend/.env (env_file in docker-compose.yml).

# ---------- 1. build the web UI ----------
FROM node:24-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm test && npm run build

# ---------- 2. runtime ----------
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/models PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.lock ./
# CPU-only PyTorch keeps the image ~1.5 GB smaller than the default CUDA build
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.lock

COPY backend/ ./backend/
COPY --from=web /web/dist ./frontend/dist

# Bake the multilingual embedding model into the image so the container starts offline and fast
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')" \
 && useradd --create-home --uid 10001 civic && chown -R civic /app /models
ENV HF_HUB_OFFLINE=1
USER civic
WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
