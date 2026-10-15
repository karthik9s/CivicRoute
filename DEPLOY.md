# Deploying CivicRoute online (Render, free, no card)

Render builds the project's `Dockerfile` straight from GitHub. No database is needed: the ~200-chunk index lives in memory and is rebuilt from the official pages during every build. The app uses about 270 MB of memory (peak about 370 MB), so it fits Render's free 512 MB instance; this was tested locally with the same 512 MB / 0.1 CPU limits. You get a public HTTPS URL like `https://civicroute.onrender.com`.

## One-time setup (about 5 minutes)

1. **Sign up** at https://dashboard.render.com/register with **GitHub**. Allow Render access to the `karthik9s/CivicRoute` repository only, not all repositories.
2. **Create the service from the Blueprint:** go to https://dashboard.render.com/blueprints, click **New Blueprint Instance**, then pick the **CivicRoute** repository. Render reads `render.yaml` and shows one free web service, **civicroute**.
3. **Enter your AI key** when Render asks for `GROQ_API_KEY`. Paste your key from https://console.groq.com/keys there. It's stored encrypted by Render and never goes into git or the build logs.
4. Click **Apply**. The first build takes about 5–10 minutes (it installs packages, downloads the AI model and crawls the official pages). When the service shows **Live**, open its URL.

If the name `civicroute` is taken, Render adds a suffix to the URL; the dashboard shows the exact address.

## Updates

Every push to `main` redeploys automatically, but **only after the GitHub CI passes** (backend tests, frontend tests and both security audits). A failing commit never goes live.

## What's configured for public use

| Setting (in `Dockerfile`; override in Render → Environment) | Default | Why |
|---|---|---|
| `LLM_DAILY_BUDGET` | `900` | Shared daily cap on AI calls so visitors can't exhaust the free Groq quota (1,000/day). After the cap, answers quote the official sources directly. |
| `PUBLIC_MODE` | `1` | `/api/health` doesn't reveal providers or models |
| `FORWARDED_ALLOW_IPS` | `*` | Trust Render's proxy, so rate limits (10 chats/min, 200/day) apply per real visitor |
| `VECTOR_STORE` | `memory` | No database to run or pay for |
| `EMBEDDING_BACKEND` | `onnx` | int8 ONNX model: same retrieval results as PyTorch, about 4× less memory |
| `SYNC_ON_START` | `0` | The search index is built during the image build, so startup skips re-indexing |

Security headers, the content-security policy, input limits, Aadhaar rejection and PII redaction are always on (see SECURITY.md).

## Good to know

- **Sleeping:** free services sleep after 15 minutes without visitors. The next visitor waits about 2 minutes while it wakes (the free CPU is small), and then answers take about 2 seconds. Free instances get 750 hours a month, enough for one service running all the time.
- **Slow CPU:** free instances get 0.1 CPU. Search still takes about a second, and the AI answer itself is produced on Groq's servers. A paid instance ($7/month at the time of writing) starts in seconds and never sleeps.
- **Updating content:** edit `backend/data/services.json`, run `python -m ingest.translate` locally (for Hindi and Telugu), commit and push. Each deploy also re-crawls the official pages.
- **Rollback:** in Render, open the service → **Events**, choose an earlier deploy → **Rollback**.
- **Own domain:** Render → service → **Settings → Custom Domains** (free; you only pay for the domain itself).
- **Other hosts:** the same image runs on Google Cloud Run, Koyeb, Fly.io or any VPS: `docker build -t civicroute . && docker run -p 8000:8000 -e GROQ_API_KEY=... civicroute`.
