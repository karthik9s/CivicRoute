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
    typo: 'Format is correct (XXXX XXXX {l4}). Our quick check-digit test did not match, so please compare it once with your Aadhaar card (tap "Show"). If it matches your card, it is fine: the official portal confirms it with UIDAI.',
    ok: (l4) => `Looks correct (XXXX XXXX ${l4}). It stays on this device.`,
  },
  hi: {
    count: (n) => `12 में से ${n} अंक दर्ज किए गए।`,
    start: 'आधार नंबर कभी 0 या 1 से शुरू नहीं होता। पहला अंक जाँचें।',
    typo: 'फ़ॉर्मेट सही है (XXXX XXXX {l4})। हमारी चेक-अंक जाँच मेल नहीं खाई, इसलिए एक बार अपने आधार कार्ड से मिला लें ("दिखाएँ" दबाएँ)। अगर कार्ड से मेल खाता है, तो सब ठीक है: आधिकारिक पोर्टल इसे UIDAI से पुष्टि करता है।',
    ok: (l4) => `सही लगता है (XXXX XXXX ${l4})। यह इसी डिवाइस पर रहता है।`,
  },
  te: {
    count: (n) => `12 అంకెలలో ${n} నమోదు చేశారు.`,
    start: 'ఆధార్ నంబర్ ఎప్పుడూ 0 లేదా 1తో మొదలవదు. మొదటి అంకెను చూడండి.',
    typo: 'ఫార్మాట్ సరిగ్గా ఉంది (XXXX XXXX {l4}). మా చెక్-అంకె పరీక్ష సరిపోలలేదు, కాబట్టి ఒకసారి మీ ఆధార్ కార్డుతో పోల్చండి ("చూపించు" నొక్కండి). కార్డుతో సరిపోతే అంతా సరే: అధికారిక పోర్టల్ దీన్ని UIDAIతో నిర్ధారిస్తుంది.',
    ok: (l4) => `సరిగ్గా ఉంది (XXXX XXXX ${l4}). ఇది ఈ పరికరంలోనే ఉంటుంది.`,
  },
}

// Zero of each digit set people type Aadhaar with: Arabic-Indic, Devanagari, Bengali, Gurmukhi, Gujarati, Odia, Tamil,
// Telugu, Kannada, Malayalam, full-width. Each is one character, so cursor positions don't move when converting.
const DIGIT_ZEROS = [0x660, 0x6F0, 0x966, 0x9E6, 0xA66, 0xAE6, 0xB66, 0xBE6, 0xC66, 0xCE6, 0xD66, 0xFF10]
/** Turn ०-९, ౦-౯, ０-９ etc. into 0-9 (\D would otherwise silently delete them). */
export const toAsciiDigits = (value) => (value || '').replace(/[\u0660-\u0669\u06F0-\u06F9\u0966-\u096F\u09E6-\u09EF\u0A66-\u0A6F\u0AE6-\u0AEF\u0B66-\u0B6F\u0BE6-\u0BEF\u0C66-\u0C6F\u0CE6-\u0CEF\u0D66-\u0D6F\uFF10-\uFF19]/g,
  (ch) => { const c = ch.charCodeAt(0); return String(c - DIGIT_ZEROS.filter((z) => c >= z).pop()) })

/** Digits only, at most 12, grouped like the card: "1234 5678 9012". */
export const formatAadhaar = (value) => toAsciiDigits(value).replace(/\D/g, '').slice(0, 12).replace(/(\d{4})(?=\d)/g, '$1 ')

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
  raw = toAsciiDigits(raw)
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
  const v = toAsciiDigits(value).replace(/\D/g, '')
  // Format is the only thing that blocks: 12 digits, not starting with 0 or 1.
  if (v.length !== 12) return { ok: false, level: 'error', message: M.count(v.length) }
  if (!/^[2-9]/.test(v)) return { ok: false, level: 'error', message: M.start }
  // Check digit (Verhoeff): every genuine Aadhaar passes it, but we can't see UIDAI's records, so a mismatch is only a
  // "compare with your card" note. The number is still accepted (ok: true) and is never called wrong.
  if (!aadhaarChecksumOk(v)) return { ok: true, level: 'warning', soft: true, checksum: false, message: M.typo.replace('{l4}', v.slice(-4)) }
  return { ok: true, level: 'info', checksum: true, message: M.ok(v.slice(-4)) }
}

/** Verhoeff check digit used by UIDAI. `digits` must be 12 ASCII digits. */
function aadhaarChecksumOk(digits) {
  let c = 0
  ;[...digits].reverse().forEach((ch, i) => { c = D[c][P[i % 8][+ch]] })
  return c === 0
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

/** Acknowledgement / coupon number without spaces, or null if it can't be one (Protean: 15 digits; UTIITSL: letters+digits). */
export function normalizeAck(value) {
  const v = (value || '').replace(/[\s-]/g, '').toUpperCase()
  return /^[A-Z0-9]{6,20}$/.test(v) ? v : null
}

/** Today as YYYY-MM-DD in local time (for date inputs' max). */
export const todayISO = () => { const d = new Date(); return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10) }

const STORE_KEY = 'civicroute.tracker'
export const tracker = {
  list() { try { return JSON.parse(localStorage.getItem(STORE_KEY)) || [] } catch { return [] } },
  save(items) {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(items)) } catch { /* private mode */ }
    window.dispatchEvent(new Event('cr-tracker'))  // lets an open "My applications" page refresh (e.g. saved from the chat)
  },
  add(item) { const items = tracker.list(); items.unshift({ ...item, id: Date.now(), created: new Date().toISOString() }); tracker.save(items); return items },
  remove(id) { const items = tracker.list().filter((i) => i.id !== id); tracker.save(items); return items },
}
