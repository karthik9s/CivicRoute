// Client-only checks for data that must never leave the device (Aadhaar) and for files.

const D = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],
  [4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],
  [8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]]
const P = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],
  [9,4,5,3,1,2,7,6,0,8],[4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]

export function validateAadhaar(value) {
  const v = (value || '').replace(/[\s-]/g, '')
  if (!/^[2-9]\d{11}$/.test(v)) return { ok: false, level: 'error', message: 'Aadhaar must be 12 digits and cannot start with 0 or 1.' }
  let c = 0
  ;[...v].reverse().forEach((ch, i) => { c = D[c][P[i % 8][+ch]] })
  if (c !== 0) return { ok: false, level: 'error', message: 'This number fails the Aadhaar checksum — check for a typo.' }
  return { ok: true, level: 'info', message: `Looks valid (XXXX XXXX ${v.slice(-4)}). Not sent or stored anywhere.` }
}

export function checkImage(file, spec) {
  return new Promise((resolve) => {
    if (!file) return resolve(null)
    const issues = []
    const kb = file.size / 1024
    const ext = file.name.split('.').pop().toLowerCase()
    if (spec.formats && !spec.formats.includes(ext)) issues.push(`Use ${spec.formats.join('/').toUpperCase()} format (this is .${ext}).`)
    if (spec.max_kb && kb > spec.max_kb) issues.push(`File is ${kb.toFixed(0)} KB — must be ≤ ${spec.max_kb} KB. Compress or resize it.`)
    if (spec.min_kb && kb < spec.min_kb) issues.push(`File is only ${kb.toFixed(1)} KB — it may be too blurry.`)
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      const want = spec.width_cm / spec.height_cm
      const got = img.width / img.height
      if (Math.abs(got - want) / want > 0.15) {
        issues.push(`Shape should be about ${spec.width_cm}×${spec.height_cm} cm (${want > 1 ? 'landscape' : 'portrait'}). Yours is ${img.width}×${img.height}px.`)
      }
      const minPx = Math.round((spec.width_cm / 2.54) * (spec.dpi || 200) * 0.6)
      if (img.width < minPx) issues.push(`Resolution looks low (${img.width}px wide). Scan at ${spec.dpi || 200} dpi.`)
      resolve({ ok: issues.length === 0, issues, preview: url, kb: kb.toFixed(1), dims: `${img.width}×${img.height}` })
    }
    img.onerror = () => resolve({ ok: false, issues: ['Could not read this image.'], preview: null })
    img.src = url
  })
}

const STORE_KEY = 'civicroute.tracker'
export const tracker = {
  list() { try { return JSON.parse(localStorage.getItem(STORE_KEY)) || [] } catch { return [] } },
  save(items) { try { localStorage.setItem(STORE_KEY, JSON.stringify(items)) } catch { /* private mode */ } },
  add(item) { const items = tracker.list(); items.unshift({ ...item, id: Date.now(), created: new Date().toISOString() }); tracker.save(items); return items },
  remove(id) { const items = tracker.list().filter((i) => i.id !== id); tracker.save(items); return items },
}
