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
# CPU-only PyTorch keeps the image ~1.5 GB smaller than the default CUDA build
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.lock

COPY backend/ ./backend/
COPY --from=web /web/dist ./frontend/dist

# Bake the multilingual embedding model into the image so the container starts offline and fast
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"

# Crawl the official sources and build the search index at build time (raw pages are not in git).
# If a site is down the build still succeeds using the reviewed service cards + curated guides.
WORKDIR /app/backend
RUN VECTOR_STORE=memory HF_HUB_OFFLINE=1 python -m ingest.run || echo "WARNING: crawl failed - using cards + KB only"

# Hugging Face Spaces runs containers as uid 1000; own everything the app writes at runtime.
RUN useradd --create-home --uid 1000 civic && chown -R civic /app /models
USER civic

# Production defaults (override with env vars / Space settings):
#  VECTOR_STORE=memory      no external database needed (~200 chunks fit easily in memory)
#  PUBLIC_MODE=1            /api/health does not reveal providers or models
#  LLM_DAILY_BUDGET=900     shared daily cap on AI calls - protects a free Groq key (1,000 requests/day)
#  FORWARDED_ALLOW_IPS=*    trust the platform proxy's X-Forwarded-For so rate limits apply per real visitor
ENV HF_HUB_OFFLINE=1 VECTOR_STORE=memory PUBLIC_MODE=1 LLM_DAILY_BUDGET=900 FORWARDED_ALLOW_IPS=* \
    LLM_PROVIDER=auto GROQ_MODEL=openai/gpt-oss-120b CORS_ORIGINS=
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
