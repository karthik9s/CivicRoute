# Deploying CivicRoute online (Hugging Face Spaces, free)

The Space builds the project's `Dockerfile`. It needs no database: the ~200-chunk index lives in memory and is rebuilt from the official pages during every build. You'll get a public HTTPS URL like `https://<hf-username>-civicroute.hf.space`.

## One-time setup (about 5 minutes)

1. **Create a Hugging Face account** at https://huggingface.co/join.
2. **Create the Space** at https://huggingface.co/new-space:
   - Space name: `civicroute`
   - SDK: **Docker**, then template **Blank**
   - Hardware: **CPU basic (free)**
   - Visibility: **Public**
3. **Add your AI key as a secret.** In the Space, go to **Settings → Variables and secrets → New secret**:
   - Name: `GROQ_API_KEY`
   - Value: your key from https://console.groq.com/keys

   Secrets are encrypted and never visible in the code or the build logs. *Never put the key in a file in the repository.*
4. **Create an access token** at https://huggingface.co/settings/tokens: **New token**, type **Write**. Copy it.
5. **Push the code**, from `C:\Users\karth\civicroute` in your terminal:
   ```bash
   git remote add hf https://huggingface.co/spaces/<hf-username>/civicroute
   git push --force hf main
   ```
   When asked, the username is your Hugging Face username and the password is the **token** from step 4. `--force` is needed only this first time, to replace the Space's template commit.
6. Open the Space's **Logs → Build** tab. The first build takes about 10–15 minutes (it installs PyTorch, downloads the AI model and crawls the official pages). When it shows **Running**, the site is live.

## Automatic deploys from GitHub (recommended)

After this, every push to GitHub that passes all tests updates the live site automatically.

1. On GitHub, go to **karthik9s/CivicRoute → Settings → Secrets and variables → Actions**:
   - **Secrets** tab → New repository secret: `HF_TOKEN` = the write token from step 4
   - **Variables** tab → New repository variable: `HF_SPACE` = `<hf-username>/civicroute`
2. From then on, just run `git push`. The CI runs the backend and frontend tests and both security audits, then deploys.

## What's configured for public use

| Setting (in `Dockerfile`, override in Space → Settings → Variables) | Default | Why |
|---|---|---|
| `LLM_DAILY_BUDGET` | `900` | Shared daily cap on AI calls so visitors can't exhaust the free Groq quota (1,000/day). After the cap, answers quote the official sources directly. |
| `PUBLIC_MODE` | `1` | `/api/health` doesn't reveal providers or models |
| `FORWARDED_ALLOW_IPS` | `*` | Trust the platform proxy, so rate limits (10 chats/min, 200/day) apply per real visitor |
| `VECTOR_STORE` | `memory` | No database to run or pay for |

Security headers, the content-security policy, input limits, Aadhaar rejection and PII redaction are always on (see SECURITY.md).

## Good to know

- **Sleeping:** free Spaces pause after 48 hours without visitors. The next visitor waits about 1–2 minutes while it wakes, and then it's fast. Upgrading the Space hardware removes this.
- **Updating content:** edit `backend/data/services.json`, run `python -m ingest.translate` locally (for Hindi and Telugu), commit and push. Rebuilding also re-crawls the official pages, so data refreshes on every deploy.
- **Rollback:** push an older commit with `git push --force hf <commit>:main`, or revert on GitHub.
- **Own domain:** Spaces doesn't support custom domains on the free tier. For `civicroute.in`-style domains, run the same Docker image on Google Cloud Run or Render.
