const BASE = import.meta.env.VITE_API_BASE || ''

const WAKING = new Set([502, 503, 504]) // the host answers these while a sleeping server starts
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function req(path, opts = {}) {
  // Reads are safe to repeat, so retry them while the server wakes up (about 15 s in total).
  const tries = opts.method && opts.method !== 'GET' ? 1 : 4
  let res
  for (let i = 0; i < tries; i++) {
    try {
      res = await fetch(BASE + path, {
        headers: { 'Content-Type': 'application/json' },
        ...opts,
        body: opts.body ? JSON.stringify(opts.body) : undefined,
      })
      if (!WAKING.has(res.status) || i === tries - 1) break
    } catch (err) {
      if (i === tries - 1) throw err
    }
    await sleep(2000 * 2 ** i)
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`
    try { msg = (await res.json()).detail || msg } catch { /* ignore */ }
    throw new Error(msg)
  }
  return res.json()
}

export const api = {
  health: () => req('/api/health'),
  meta: () => req('/api/meta'),
  problems: () => req('/api/problems'),
  updates: (lang = 'en') => req(`/api/updates?lang=${lang}`),
  support: (lang = 'en') => req(`/api/support?lang=${lang}`),
  question: (id) => req(`/api/flow/${id}`),
  services: (lang = 'en') => req(`/api/services?lang=${lang}`),
  service: (id, lang = 'en') => req(`/api/services/${id}?lang=${lang}`),
  intent: (text, lang = 'en') => req(`/api/intent?lang=${lang}`, { method: 'POST', body: { text } }),
  chat: (question, service_id, lang, history) =>
    req('/api/chat', { method: 'POST', body: { question, service_id, lang, history } }),
  validate: (service_id, values) => req('/api/validate', { method: 'POST', body: { service_id, values } }),
  handoff: (service_id, values, lang = 'en') => req(`/api/handoff?lang=${lang}`, { method: 'POST', body: { service_id, values } }),
}
