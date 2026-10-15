# CivicRoute — PAN Help Desk

An AI-assisted help desk that guides Indian citizens through **PAN services** (new PAN, correction, duplicate/reprint, e-PAN, Aadhaar linking, tracking, verification, duplicate-PAN surrender). Citizens describe a problem in their own words (English, हिंदी, తెలుగు), get the correct service with steps, documents and fees **from official sources**, have their details checked before applying, and finish on the **official portal**.

> CivicRoute is **not a Government website**. It never submits applications, takes payments, or handles OTPs or Aadhaar numbers. Citizens sign and pay on the official portal themselves, so CivicRoute can't be cloned into a phishing page, and fake look-alike PAN sites are a real problem it helps people avoid.

## Features

| Area | What it does |
|---|---|
| **Find the right service** | Free-text search with intent detection (EN/HI/TE/Hinglish), "common problems" decision trees, 9 PAN services |
| **Grounded answers (RAG)** | Hybrid retrieval (pgvector cosine + full-text, Reciprocal Rank Fusion) over crawled official pages + human-reviewed service cards; LLM answers **only from cited sources** |
| **AI support agent** | Chat widget for questions and problems (payment not reflecting, rejection, card not delivered), guided questions, a conversational form, and verified official helplines |
| **Application prep** | Government-style multi-step form: PAN format and surname-initial checks, name-vs-proof mismatch, DOB, mobile, PIN, photo/signature size checks; printable summary mapped to the official form's field names |
| **Official-only facts** | A fee is shown only if an official page states it (each fee links to its source); otherwise "shown on the official payment page" |
| **Updates feed** | Dated policy/link updates; the crawler flags changed official pages automatically ("Changed"/"Review") |
| **Languages** | English, Hindi, Telugu across the UI, service content, chat and policies. Machine translations pass a fact check (numbers, ₹, URLs, key terms must match the English) |
| **Accessibility (GIGW / WCAG 2.1 AA)** | Skip link, text size A-/A/A+, Day/Night theme, high-contrast mode, keyboard focus, screen-reader labels, reduced motion, mobile layout |
| **Tracker** | Saves acknowledgement numbers in the browser only, with links to official tracking pages |
| **Security** | See [SECURITY.md](SECURITY.md): CSP and security headers, rate limiting, input limits, Aadhaar rejection, PII redaction before the LLM, link allow-list on AI output, localhost-only DB |

## Architecture

```
official sources (incometax.gov.in, proteantech.in, utiitsl.com; EN/HI)        data/services.json (reviewed cards)
   │ ingest/crawler.py: allow-list (re-checked after redirects), robots.txt,       data/kb/*.md (curated guides)
   │ rate limit, change detection                                              data/i18n/services.{hi,te}.json
   ▼                                                                           (translations, fact-checked)
data/raw ─► ingest/chunker.py ─► multilingual-e5-small embeddings ─► pgvector (HNSW + tsvector) │ local file index fallback
                                                                         ▼
FastAPI (backend/app) ── /api/intent      keyword rules + embeddings → service (localized titles)
                     ── /api/chat        intent-scoped hybrid retrieval + service card → LLM with [n] citations
                     │                   (Groq / Claude / xAI / Gemini / OpenAI, or extractive fallback without a key)
                     ── /api/validate    field + cross-field checks (Aadhaar-like numbers rejected)
                     ── /api/handoff     summary sheet: official field label → value, checklist, fees, safety
                     ── /api/services, /api/updates, /api/support   (?lang=en|hi|te)
                     ▼
React + Vite (frontend/src) — government-portal layout + Help Desk chat widget (src/chat)
```

## Quick start (Windows)

Double-click **`start.bat`** (or run it from any terminal). Stop with Ctrl+C, or double-click **`stop.bat`**.

`start.bat` installs missing Python packages, starts Docker Desktop and the pgvector database if available (otherwise it uses the built-in local index), syncs the index, reuses or restarts an existing app or picks a free port, and opens the browser when the app is ready. Options: `-NoDocker`, `-Port 8080`, `-NoBrowser`.

### One-time setup

1. **Python 3.11+** and **Node 20+** installed.
2. Backend packages: `cd backend` then `python -m pip install -r requirements.lock`
3. AI key (optional, free): get a key at https://console.groq.com/keys and put it in `backend/.env`:
   ```
   LLM_PROVIDER=groq
   GROQ_API_KEY=gsk_...
   ```
   See `.env.example` for Anthropic / xAI / Gemini / OpenAI. Without a key, answers are quoted directly from sources.
4. Web UI: `cd frontend`, then `npm ci`, then `npm run build` (the backend serves `frontend/dist`).
5. Optional database: Docker Desktop, then `docker compose up -d` from the project folder.

**Docker is optional.** For about 200 chunks the local index gives the same results. If Docker Desktop shows an error dialog at startup (stale socket after sleep or shutdown), close it fully and run
`Rename-Item "$env:LOCALAPPDATA\Docker\run" ("run.stale-" + (Get-Date -Format yyyyMMddHHmmss))`; turning off Settings → AI → Docker Model Runner prevents it.

### Run everything in containers

```bash
docker compose --profile app up -d --build
```

This builds the UI and server into one image (no PyTorch: int8 ONNX embedding model baked in, ~120 MB RAM, non-root user, health check) and runs it next to pgvector. It's available at http://localhost:8000. Secrets come from `backend/.env` at runtime; they are never baked into the image.

### Put it online (free)

The repository includes a Render Blueprint (`render.yaml`): one free web service, no database, no card. Setup takes about 5 minutes; see [DEPLOY.md](DEPLOY.md).

## Keeping data fresh

```powershell
powershell -ExecutionPolicy Bypass -File scripts\refresh.ps1
```

This re-crawls the official pages, re-embeds only what changed, translates new or changed text, and lists any service cards to re-review because an official page changed. To run it every Sunday at 06:00:

```powershell
schtasks /Create /SC WEEKLY /D SUN /ST 06:00 /TN "CivicRoute refresh" /TR "powershell -ExecutionPolicy Bypass -File C:\Users\karth\civicroute\scripts\refresh.ps1"
```

Editing content: change `backend/data/services.json` (English is authoritative), then run `python -m ingest.translate` in `backend` to update Hindi and Telugu. Add official sources in `backend/ingest/sources.yaml`.

## Tests and quality

| Command | Covers |
|---|---|
| `cd backend` then `python -m pytest` | 44 tests: validators, intent routing, API, localization (facts unchanged across languages), security controls (headers, rate limit, size limit, Aadhaar rejection, redaction, link allow-list, crawler allow-list) |
| `cd frontend` then `npm test` | Browser-side Aadhaar checksum, fee labels, **translation completeness** (every label in all 3 languages) |
| `cd backend` then `python -m eval.run_eval` | 32-question golden set in EN/HI/TE: intent accuracy, retrieval hit rate, required facts, citations |
| `python -m pip_audit -r backend/requirements.lock` / `npm audit` | Dependency vulnerabilities (both currently clean) |

CI (`.github/workflows/ci.yml`) runs the backend tests, the frontend tests and build, and both audits on every push, plus a weekly audit.

**Latest evaluation** (2026-10-15 · Groq `openai/gpt-oss-120b` · 32 questions in English, Hindi and Telugu):

| Metric | Score |
|---|---|
| Right service picked first | 96.6% |
| Right service in top 3 | 100% |
| Retrieved chunks from the right service | 100% |
| Answer contains every required fact | 100% |
| Answers with citations | 100% |

The one routing miss, "Can I change my delivery address while ordering a reprint?", goes to *correction* first. That's arguably also helpful, since changing the address does need a correction.

## Project layout

```
backend/   app/ (API, RAG, intent, validators, security, i18n)  ingest/ (crawler, chunker, translate)
           data/ (service cards, flows, KB, translations, helplines, updates)  eval/  tests/
frontend/  src/pages (Home, ServicePage, Apply, Tracker, Info)  src/chat (support agent)  src/lib (api, i18n, validation)
scripts/   refresh.ps1 (weekly data refresh), test_opener.ps1
start.bat / start.ps1 / stop.bat · Dockerfile · docker-compose.yml · render.yaml · DEPLOY.md · SECURITY.md
```

## Maintenance

- **Upgrading Python packages:** update `requirements.txt` ranges, install, run the tests, then regenerate `requirements.lock` with the exact installed versions and run `pip-audit`.
- **Groq retires models regularly:** the app switches to another available model automatically. Set `GROQ_MODEL` in `.env` to make it permanent.
- **Before hosting publicly**, see the "Accepted risks" table in [SECURITY.md](SECURITY.md): TLS reverse proxy, a shared rate limiter, a strong DB password, and a privacy notice for the AI provider.

## Disclaimer

CivicRoute is an independent helper and is not affiliated with the Income Tax Department, Protean or UTIITSL. Always confirm on the official portal.
