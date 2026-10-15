# CivicRoute — Security & Risk Decisions

CivicRoute helps citizens with PAN services, so it handles identity data and must never become a phishing or data-leak vector. This document covers what we protect, against whom, and why each control exists. Every control listed as *tested* has a regression test in `backend/tests/test_security.py`.

## 1. Threat model

| Asset | Threat | Who |
|---|---|---|
| Citizens' identity data (Aadhaar, PAN, DOB, name, address, mobile, email) | Collection, leakage to AI providers, logs or attackers | Malicious users, compromised infrastructure, third-party AI providers |
| Trust: "only official links, only official fees" | Prompt injection makes the AI recommend scam sites or wrong fees | Malicious users, poisoned web pages |
| API keys (Groq/Anthropic/…), database | Theft, quota exhaustion | Network attackers, abusive clients |
| The server | Denial of service, path traversal, SSRF via the crawler | Remote attackers |

## 2. Core design decisions (risk avoided by design)

1. **CivicRoute never submits applications, takes payments or handles OTPs.** The citizen signs and pays on the official portal. This removes the highest-risk features entirely: there's no payment data, no credential storage, and nothing that could be cloned into a phishing page.
2. **Aadhaar never reaches the server.** It is validated only in the browser (Verhoeff checksum). The API rejects any value that looks like an Aadhaar number or 16-digit Virtual ID under any field name (*tested*).
3. **Stateless server.** Nothing typed into the wizard is stored or logged. API responses are sent with `Cache-Control: no-store`. The application tracker uses the browser's `localStorage` only and holds just acknowledgement numbers.
4. **Fees and links come only from official sources.** Service cards are human-reviewed. A fee is quoted only when an official page states it (each fee carries a `source` URL); otherwise the app says it's shown on the official payment page.

## 3. Controls

### Privacy / data protection
| Control | Where | Status |
|---|---|---|
| Redact Aadhaar, Aadhaar VID, PAN, mobile, OTP/PIN and email from chat **before** any LLM call (question and history) | `app/rag.py: redact()` | tested |
| Server rejects Aadhaar-like numbers in any field (400) | `app/main.py: _reject_sensitive()` | tested |
| Aadhaar field is `type=password`, `autocomplete=off`, kept only in component memory | `frontend/src/pages/Wizard.jsx` | — |
| Photo/signature checks run in the browser; files are never uploaded | `frontend/src/lib/validate.js` | — |
| `Referrer-Policy: no-referrer` + `rel="noopener noreferrer"` on all external links | middleware, React | tested |

### AI / prompt-injection safety
| Control | Status |
|---|---|
| System prompt: answer only from numbered official sources, cite them, never invent steps/fees/URLs, never ask for Aadhaar/PAN/OTP | — |
| **Output link allow-list**: any URL not on a government/agency domain is removed from answers, whatever the model says. This guards against injection from users *and* from crawled pages | tested |
| Citations limited to official URLs | tested |
| Chat history only accepts `user`/`assistant` roles (no client-supplied `system` turns) and at most 8 turns | tested |
| `lang` parameter is restricted to a known list (it is interpolated into the prompt) | — |
| Verified manually: an injection asking the AI to promote a fake "pan-fasthelp.xyz" site was refused, and the link filter would have stripped it anyway | manual |

### API hardening
| Control | Status |
|---|---|
| Security headers: strict CSP (`default-src 'self'`, `frame-ancestors 'none'`, no inline scripts), `X-Frame-Options: DENY`, `nosniff`, `Permissions-Policy`, `COOP` | tested |
| Request body limit 64 KB (413); `Content-Length` required on writes | tested |
| Strict input schemas: field counts, value lengths, `service_id` pattern `^[a-z_]+$` | tested |
| Rate limiting per client: chat 10/min and 200/day (protects the free LLM quota); other POSTs 120/min | tested |
| CORS: only the local dev origin, `GET`/`POST`, no credentials | tested (probe) |
| Interactive API docs (`/docs`, `/openapi.json`) disabled | tested |
| Static file serving resolves paths and refuses anything outside `frontend/dist` (traversal attempts return the app page, never files like `.env`) | probed |
| Server binds to `127.0.0.1` only | — |

### Secrets & infrastructure
| Control | Status |
|---|---|
| API keys live only in `backend/.env`, which git ignores (verified with `git check-ignore`) | verified |
| The Anthropic client pins `https://api.anthropic.com` so an ambient `ANTHROPIC_BASE_URL` (e.g. a desktop-app proxy) never receives the key; only an explicit `ANTHROPIC_API_KEY` is used, never ambient session tokens | — |
| Groq/xAI clients use fixed official base URLs | tested |
| **Database bound to `127.0.0.1:5433`.** Previously it listened on all interfaces, which exposed it to the local network with the default password. Set `POSTGRES_PASSWORD` in a root `.env` for a strong password | fixed + verified |
| `start.bat` / `stop.bat` only stop processes whose command line contains this project's path, so they never kill other Python apps | — |

### Crawler (SSRF / supply of content)
| Control | Status |
|---|---|
| Domain allow-list (government + appointed agencies), checked **again after redirects** | tested |
| robots.txt respected, 1.5 s delay, 30 s timeout, 15 MB size cap, TLS verification on | — |
| Changes on official pages are detected and the affected service cards are flagged for human re-review | — |

### Dependencies
| Check | Result (2026-10-14) |
|---|---|
| `pip-audit -r backend/requirements.lock` | No known vulnerabilities (2026-10-15) |
| `npm audit` (frontend) | **0 vulnerabilities** after upgrading Vite 5.4.11 → 7.3.6 (fixed GHSA-4w7w-66w2-5vf9, GHSA-fx2h-pf6j-xcff, GHSA-v6wh-96g9-6wx3, which were dev-server path-traversal / hash-disclosure issues) |

Re-run both before every release:
```bash
python -m pip_audit -r backend/requirements.txt
cd frontend && npm audit
```

## 4. Accepted risks and what to do before going public

These are acceptable for a local or demo deployment and **must** be addressed before hosting it publicly:

| Risk | Why accepted now | Before going public |
|---|---|---|
| Rate limiter is in-memory and per-process; uses the socket IP | Single local process | Use Redis-backed limits; read the client IP from a trusted reverse proxy only |
| No HTTPS / HSTS | Runs on localhost | Terminate TLS at a reverse proxy (Caddy/Nginx), add `Strict-Transport-Security` |
| ~~Unpinned Python versions~~ **Done:** `backend/requirements.lock` pins exact versions; CI audits weekly | — | Enable Dependabot for automatic upgrade PRs |
| Chat text is sent to a third-party LLM (Groq/Anthropic/xAI) | Identifiers are redacted first | Publish a privacy notice; prefer providers with zero-retention options |
| `/api/health` reveals provider/model names locally | Useful for local debugging; `PUBLIC_MODE=1` (default in the Docker image) hides them | — |
| Default DB password `civicroute` | DB is localhost-only | Set `POSTGRES_PASSWORD`; use a managed DB with network rules |
| `start.ps1` auto-installs packages from PyPI (`requirements.txt`) | Convenience on first run | Use `requirements.lock` / the Docker image in production |
| Docker image tag `pgvector/pgvector:pg16` isn't pinned to a digest | Official image | Pin by digest |

## 5. Reporting

Found a problem? Don't post Aadhaar/PAN data in issues. Contact the maintainer privately.
