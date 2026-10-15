# CivicRoute - single container: React build served by the FastAPI app.
#   Local:   docker compose --profile app up -d --build      (app + pgvector)
#   Public:  Hugging Face Spaces (Docker SDK) builds this file directly - see DEPLOY.md
# Secrets are NOT baked in: pass them at runtime (backend/.env locally, Space secrets on Hugging Face).

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
# No PyTorch: embeddings run on ONNX Runtime (int8), so the app fits in 512 MB of RAM
RUN pip install -r requirements.lock

COPY backend/ ./backend/
COPY --from=web /web/dist ./frontend/dist

# Bake the multilingual embedding model into the image so the container starts offline and fast
RUN cd backend && python -c "from app.embeddings import get_embedder; e = get_embedder(); assert 'onnx' in e.name, e.name"

# Crawl the official sources and build the search index at build time (raw pages are not in git).
# If a site is down the build still succeeds using the reviewed service cards + curated guides.
WORKDIR /app/backend
RUN VECTOR_STORE=memory HF_HUB_OFFLINE=1 python -m ingest.run || echo "WARNING: crawl failed - using cards + KB only"

# Run as an unprivileged user (uid 1000); own everything the app writes at runtime.
RUN useradd --create-home --uid 1000 civic && chown -R civic /app /models
USER civic

# Production defaults (override with env vars / Render dashboard):
#  VECTOR_STORE=memory      no external database needed (~200 chunks fit easily in memory)
#  SYNC_ON_START=0          the index above is already current; start in seconds on small CPUs
#  PUBLIC_MODE=1            /api/health does not reveal providers or models
#  LLM_DAILY_BUDGET=900     shared daily cap on AI calls - protects a free Groq key (1,000 requests/day)
#  FORWARDED_ALLOW_IPS=*    trust the platform proxy's X-Forwarded-For so rate limits apply per real visitor
ENV HF_HUB_OFFLINE=1 VECTOR_STORE=memory SYNC_ON_START=0 PUBLIC_MODE=1 LLM_DAILY_BUDGET=900 FORWARDED_ALLOW_IPS=* \
    LLM_PROVIDER=auto GROQ_MODEL=openai/gpt-oss-120b CORS_ORIGINS=
#  PORT                     hosts like Render inject the port to listen on; 8000 locally
ENV PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s   CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ['PORT'], timeout=4)"
CMD ["sh", "-c", "exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers"]
