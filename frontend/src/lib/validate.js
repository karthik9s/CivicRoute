// Client-only checks for data that must never leave the device (Aadhaar) and for files.

const D = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],
  [4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],
  [8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]]
const P = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],
  [9,4,5,3,1,2,7,6,0,8],[4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]

const AADHAAR_MSG = {
  en: {
    count: (n) => `${n} of 12 digits entered.`,
    start: 'An Aadhaar number never starts with 0 or 1. Check the first digit.',
    typo: 'This is not a valid Aadhaar number: one digit is probably wrong or two digits are swapped. Tap "Show" and compare it, 4 digits at a time, with your Aadhaar card, e-Aadhaar or mAadhaar app.',
    ok: (l4) => `Looks correct (XXXX XXXX ${l4}). It stays on this device.`,
  },
  hi: {
    count: (n) => `12 में से ${n} अंक दर्ज किए गए।`,
    start: 'आधार नंबर कभी 0 या 1 से शुरू नहीं होता। पहला अंक जाँचें।',
    typo: 'यह मान्य आधार नंबर नहीं है: शायद एक अंक गलत है या दो अंक आपस में बदल गए हैं। "दिखाएँ" दबाएँ और अपने आधार कार्ड, ई-आधार या mAadhaar ऐप से 4-4 अंक मिलाएँ।',
    ok: (l4) => `सही लगता है (XXXX XXXX ${l4})। यह इसी डिवाइस पर रहता है।`,
  },
  te: {
    count: (n) => `12 అంకెలలో ${n} నమోదు చేశారు.`,
    start: 'ఆధార్ నంబర్ ఎప్పుడూ 0 లేదా 1తో మొదలవదు. మొదటి అంకెను చూడండి.',
    typo: 'ఇది సరైన ఆధార్ నంబర్ కాదు: బహుశా ఒక అంకె తప్పుగా ఉంది లేదా రెండు అంకెలు అటూ ఇటూ మారాయి. "చూపించు" నొక్కి, మీ ఆధార్ కార్డు, ఇ-ఆధార్ లేదా mAadhaar యాప్‌తో 4-4 అంకెలుగా పోల్చి చూడండి.',
    ok: (l4) => `సరిగ్గా ఉంది (XXXX XXXX ${l4}). ఇది ఈ పరికరంలోనే ఉంటుంది.`,
  },
}

/** Digits only, at most 12, grouped like the card: "1234 5678 9012". */
export const formatAadhaar = (value) => (value || '').replace(/\D/g, '').slice(0, 12).replace(/(\d{4})(?=\d)/g, '$1 ')

/**
 * Apply one edit to the grouped Aadhaar field and keep the cursor where the user is editing.
 * Without this, regrouping the digits jumps the cursor to the end, so a digit typed while fixing a
 * typo in the middle lands at the end and scrambles the number.
 * @param prev   value before the edit ("9999 4155 7058")
 * @param raw    what the browser put in the input after the edit
 * @param caret  cursor position in `raw` after the edit
 * @param inputType  InputEvent.inputType (deleting across a space must still delete a digit)
 */
export function editAadhaar(prev, raw, caret, inputType = '') {
  let digits = raw.replace(/\D/g, '')
  let before = raw.slice(0, caret).replace(/\D/g, '').length  // digits to the left of the cursor
  if (digits === (prev || '').replace(/\D/g, '')) {  // only a space was removed
    if (inputType === 'deleteContentBackward' && before > 0) { digits = digits.slice(0, before - 1) + digits.slice(before); before -= 1 }
    else if (inputType === 'deleteContentForward') digits = digits.slice(0, before) + digits.slice(before + 1)
  }
  digits = digits.slice(0, 12)
  before = Math.min(before, digits.length)
  const value = formatAadhaar(digits)
  let pos = 0
  for (let n = 0; pos < value.length && n < before; pos++) if (/\d/.test(value[pos])) n++
  return { value, caret: pos }
}

export function validateAadhaar(value, lang = 'en') {
  const M = AADHAAR_MSG[lang] || AADHAAR_MSG.en
  const v = (value || '').replace(/\D/g, '')
  if (v.length !== 12) return { ok: false, level: 'error', message: M.count(v.length) }
  if (!/^[2-9]/.test(v)) return { ok: false, level: 'error', message: M.start }
  let c = 0
  ;[...v].reverse().forEach((ch, i) => { c = D[c][P[i % 8][+ch]] })
  if (c !== 0) return { ok: false, level: 'error', message: M.typo }
  return { ok: true, level: 'info', message: M.ok(v.slice(-4)) }
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
