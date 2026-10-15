import { useEffect, useRef, useState } from 'react'
import Icon from '../components/Icon.jsx'
import { api } from '../lib/api.js'
import { checkImage, tracker, validateAadhaar } from '../lib/validate.js'
import { Message, Typing } from './Messages.jsx'

const OPTIONAL = new Set(['mother_name', 'address_line2', 'proof_name', 'other_pans', 'photo', 'signature'])
const LOCAL_ONLY = new Set(['aadhaar_local', 'photo', 'signature'])
const STATES = ['Andaman and Nicobar Islands', 'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chandigarh', 'Chhattisgarh',
  'Dadra and Nagar Haveli and Daman and Diu', 'Delhi', 'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jammu and Kashmir', 'Jharkhand',
  'Karnataka', 'Kerala', 'Ladakh', 'Lakshadweep', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha',
  'Puducherry', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal']

const TXT = {
  en: {
    greet1: 'Namaste! 🙏 I\'m CivicRoute, your PAN assistant.',
    greet2: 'Tell me what happened in your own words, or tap one of these:',
    else: 'Something else? Just type it below — any language is fine.',
    found: 'Here\'s the service for you 👇',
    steps: 'Show me the steps', prepare: 'Prepare my application', ask: 'I have a question', other: 'Something else',
    askPrompt: (t) => `Sure — ask me anything about “${t}”. I'll answer from official sources.`,
    formIntro: (t) => `Great, let's get your details ready for “${t}”. I'll check each one so the application doesn't get rejected.`,
    formPrivacy: '🔒 Nothing you type is saved. Your Aadhaar is checked on this phone only and never sent anywhere.',
    skip: 'Skip', keep: 'Keep it, continue', change: 'Let me change it', done: 'Done',
    useAnyway: 'Use it anyway', another: 'Choose another file',
    checking: 'Checking everything one last time…',
    ack: 'Save my acknowledgement no.', ackAsk: 'After you submit on the official site, type the acknowledgement / coupon number here and I\'ll keep it for tracking.',
    ackSaved: 'Saved ✓ You can find it under “My applications”.',
    cancelled: 'No problem — I\'ve cleared those details.',
    menu: 'What else can I help with?',
    placeholder: 'Type a message', aadhaarPh: '12-digit Aadhaar (stays on this phone)',
    supportMenu: 'Problem with an application', helplines: 'Official helplines',
    supportAsk: "Sorry you're facing trouble. What went wrong?",
    supportTopics: ["I paid but the status hasn't changed", 'My application was rejected', 'My PAN card was not delivered', 'e-PAN email not received', 'Name/DOB mismatch with Aadhaar'],
    helplineIntro: 'Here are the official helplines (verified from the Income Tax “Contact us” page). Keep your acknowledgement number ready when you call.',
    stillStuck: 'Still stuck? Call an official helpline',
  },
  hi: {
    greet1: 'नमस्ते! 🙏 मैं CivicRoute हूँ, आपका PAN सहायक।',
    greet2: 'अपनी समस्या अपने शब्दों में लिखिए, या इनमें से चुनिए:',
    else: 'कुछ और? नीचे लिखिए — किसी भी भाषा में।',
    found: 'आपके लिए सही सेवा यह है 👇',
    steps: 'चरण दिखाएँ', prepare: 'आवेदन तैयार करें', ask: 'मेरा एक सवाल है', other: 'कुछ और',
    askPrompt: (t) => `ज़रूर — “${t}” के बारे में कुछ भी पूछिए। मैं आधिकारिक स्रोतों से जवाब दूँगा।`,
    formIntro: (t) => `बढ़िया, “${t}” के लिए आपकी जानकारी तैयार करते हैं। मैं हर जानकारी जाँचूँगा ताकि आवेदन अस्वीकार न हो।`,
    formPrivacy: '🔒 आपकी कोई जानकारी सहेजी नहीं जाती। आधार केवल इसी फ़ोन पर जाँचा जाता है।',
    skip: 'छोड़ें', keep: 'ठीक है, आगे', change: 'बदलना है', done: 'हो गया',
    useAnyway: 'फिर भी इस्तेमाल करें', another: 'दूसरी फ़ाइल चुनें',
    checking: 'आख़िरी बार सब जाँच रहा हूँ…',
    ack: 'पावती नंबर सहेजें', ackAsk: 'आधिकारिक साइट पर जमा करने के बाद पावती / कूपन नंबर यहाँ लिखिए, मैं ट्रैकिंग के लिए रखूँगा।',
    ackSaved: 'सहेज लिया ✓ “मेरे आवेदन” में मिलेगा।',
    cancelled: 'ठीक है — वह जानकारी हटा दी।',
    menu: 'और किस चीज़ में मदद करूँ?',
    placeholder: 'संदेश लिखें', aadhaarPh: '12 अंकों का आधार (इसी फ़ोन पर रहेगा)',
    supportMenu: 'आवेदन में समस्या', helplines: 'आधिकारिक हेल्पलाइन',
    supportAsk: 'माफ़ कीजिए, आपको दिक्कत हो रही है। क्या समस्या है?',
    supportTopics: ['भुगतान किया पर स्थिति नहीं बदली', 'मेरा आवेदन अस्वीकार हुआ', 'मेरा PAN कार्ड नहीं मिला', 'e-PAN ईमेल नहीं मिला', 'आधार से नाम/जन्मतिथि मेल नहीं खाती'],
    helplineIntro: 'ये आधिकारिक हेल्पलाइन हैं (आयकर “Contact us” पेज से सत्यापित)। कॉल करते समय पावती नंबर तैयार रखें।',
    stillStuck: 'अब भी दिक्कत? आधिकारिक हेल्पलाइन पर कॉल करें',
  },
  te: {
    greet1: 'నమస్తే! 🙏 నేను CivicRoute, మీ PAN సహాయకుడిని.',
    greet2: 'ఏం జరిగిందో మీ మాటల్లో చెప్పండి, లేదా వీటిలో ఒకటి ఎంచుకోండి:',
    else: 'ఇంకేమైనా? కింద టైప్ చేయండి — ఏ భాషలోనైనా పరవాలేదు.',
    found: 'మీకు సరైన సేవ ఇది 👇',
    steps: 'దశలు చూపించు', prepare: 'దరఖాస్తు సిద్ధం చేయండి', ask: 'నాకు ఒక ప్రశ్న ఉంది', other: 'ఇంకేదైనా',
    askPrompt: (t) => `తప్పకుండా — “${t}” గురించి ఏదైనా అడగండి. అధికారిక మూలాల నుండి సమాధానం ఇస్తాను.`,
    formIntro: (t) => `బాగుంది, “${t}” కోసం మీ వివరాలు సిద్ధం చేద్దాం. దరఖాస్తు తిరస్కరించబడకుండా ప్రతి వివరాన్ని తనిఖీ చేస్తాను.`,
    formPrivacy: '🔒 మీరు టైప్ చేసేది ఏదీ సేవ్ చేయబడదు. మీ ఆధార్ ఈ ఫోన్‌లోనే తనిఖీ చేయబడుతుంది, ఎక్కడికీ పంపబడదు.',
    skip: 'దాటవేయి', keep: 'సరే, ముందుకు', change: 'మార్చాలి', done: 'అయిపోయింది',
    useAnyway: 'అయినా వాడండి', another: 'వేరే ఫైల్ ఎంచుకోండి',
    checking: 'చివరిసారిగా అన్నీ తనిఖీ చేస్తున్నాను…',
    ack: 'నా అక్నాలెడ్జ్‌మెంట్ నంబర్ సేవ్ చేయి', ackAsk: 'అధికారిక సైట్‌లో సమర్పించిన తర్వాత, అక్నాలెడ్జ్‌మెంట్ / కూపన్ నంబర్ ఇక్కడ టైప్ చేయండి, ట్రాకింగ్ కోసం ఉంచుతాను.',
    ackSaved: 'సేవ్ అయింది ✓ “నా దరఖాస్తులు”లో చూడవచ్చు.',
    cancelled: 'పర్వాలేదు — ఆ వివరాలు తొలగించాను.',
    menu: 'ఇంకా దేనిలో సహాయం చేయగలను?',
    placeholder: 'సందేశం టైప్ చేయండి', aadhaarPh: '12 అంకెల ఆధార్ (ఈ ఫోన్‌లోనే ఉంటుంది)',
    supportMenu: 'దరఖాస్తులో సమస్య', helplines: 'అధికారిక హెల్ప్‌లైన్లు',
    supportAsk: 'మీకు ఇబ్బంది కలిగినందుకు క్షమించండి. ఏమి తప్పు జరిగింది?',
    supportTopics: ['చెల్లించాను కానీ స్థితి మారలేదు', 'నా దరఖాస్తు తిరస్కరించబడింది', 'నా PAN కార్డు రాలేదు', 'e-PAN ఈమెయిల్ రాలేదు', 'ఆధార్‌తో పేరు/పుట్టిన తేదీ సరిపోలడం లేదు'],
    helplineIntro: 'ఇవి అధికారిక హెల్ప్‌లైన్లు (ఆదాయపు పన్ను “Contact us” పేజీ నుండి ధృవీకరించబడ్డాయి). కాల్ చేసేటప్పుడు అక్నాలెడ్జ్‌మెంట్ నంబర్ సిద్ధంగా ఉంచుకోండి.',
    stillStuck: 'ఇంకా సమస్యా? అధికారిక హెల్ప్‌లైన్‌కు కాల్ చేయండి',
  },
}

const loc = (o, k, lang) => o[`${k}_${lang}`] || o[k]
const now = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
let nid = 0

export default function ChatApp({ lang, command, header, support }) {
  const L = TXT[lang] || TXT.en
  const [msgs, setMsgs] = useState([])
  const [replies, setReplies] = useState([])
  const [typing, setTyping] = useState(false)
  const [text, setText] = useState('')
  const [mode, setMode] = useState({ type: 'free' })   // free | field | ack
  const [multi, setMulti] = useState([])
  const form = useRef(null)                             // { s, fields, idx, values, aadhaar }
  const cache = useRef({ problems: [], list: {}, detail: {} })
  const wall = useRef(null)
  const input = useRef(null)
  const fileIn = useRef(null)
  const started = useRef(false)

  useEffect(() => { wall.current?.scrollTo({ top: wall.current.scrollHeight, behavior: 'smooth' }) }, [msgs, typing, replies])

  // ---------------------------------------------------------------- primitives
  const push = (m) => setMsgs((list) => [...list, { id: ++nid, t: now(), from: 'bot', ...m }])
  const me = (text, extra = {}) => push({ from: 'me', text, ...extra })
  async function bot(items, delay = 520) {
    setReplies([])
    setTyping(true)
    await sleep(delay)
    setTyping(false)
    for (const it of [].concat(items)) push(it)
  }
  const reply = (label, fn, cls = '') => ({ label, fn, cls })

  async function detail(id) {
    const key = `${id}:${lang}`
    if (!cache.current.detail[key]) cache.current.detail[key] = await api.service(id, lang)
    return cache.current.detail[key]
  }

  // ---------------------------------------------------------------- conversation
  async function greet() {
    try {
      const [problems, list] = await Promise.all([api.problems(), api.services(lang)])
      cache.current.problems = problems
      cache.current.list = Object.fromEntries(list.map((s) => [s.id, s]))
    } catch (e) {
      await bot({ text: `I can't reach the CivicRoute server (${e.message}). Is it running?`, tone: 'bad' }, 200)
      return
    }
    await bot([{ text: L.greet1, lead: true }], 400)
    await bot([{ text: L.greet2 }], 500)
    menuReplies()
  }

  function menuReplies() {
    setReplies([...cache.current.problems.map((p) => reply(loc(p, 'title', lang), () => pickProblem(p))),
      reply(`🛟 ${L.supportMenu}`, supportMenu), reply(`📞 ${L.helplines}`, () => { me(L.helplines); showHelplines() }, 'ghost')])
  }

  async function pickProblem(p) {
    me(loc(p, 'title', lang))
    if (p.result) await showService(p.result)
    else await ask(p.start)
  }

  async function ask(qid) {
    let q
    try { q = await api.question(qid) } catch (e) { return bot({ text: e.message, tone: 'bad' }) }
    await bot({ text: loc(q, 'text', lang), lead: true })
    setReplies(q.options.map((o) => reply(loc(o, 'label', lang), async () => {
      me(loc(o, 'label', lang))
      if (o.next) return ask(o.next)
      if (o.note) await bot({ text: o.note, tone: 'warn' })
      await showService(o.result)
    })))
  }

  async function showService(id, intro = L.found) {
    let s
    try { s = await detail(id) } catch (e) { return bot({ text: e.message, tone: 'bad' }) }
    await bot([{ text: intro }, { kind: 'service', s }])
    setReplies(serviceReplies(s))
  }

  const serviceReplies = (s) => [
    reply(`📋 ${L.steps}`, () => { me(L.steps); showSteps(s) }),
    reply(`✍️ ${L.prepare}`, () => startForm(s), 'primary'),
    reply(`💬 ${L.ask}`, () => askAbout(s)),
    reply(L.other, () => { me(L.other); bot({ text: L.menu }).then(menuReplies) }, 'ghost'),
  ]

  async function supportMenu() {
    me(L.supportMenu)
    await bot({ text: L.supportAsk })
    setReplies([...L.supportTopics.map((topic) => reply(topic, () => freeText(topic, true))),
      reply(`📞 ${L.helplines}`, () => { me(L.helplines); showHelplines() }, 'ghost')])
  }

  async function showHelplines() {
    await bot([{ text: L.helplineIntro }, { kind: 'helpline', lines: support?.helplines || [] }])
    setReplies([reply(L.other, () => { me(L.other); bot({ text: L.menu }).then(menuReplies) }, 'ghost')])
  }

  async function showSteps(s) {
    await bot({ kind: 'steps', s }, 650)
    setReplies([serviceReplies(s)[1], serviceReplies(s)[2], serviceReplies(s)[3]])
  }

  async function askAbout(s) {
    me(L.ask)
    await bot({ text: L.askPrompt(s.title) })
    input.current?.focus()
  }

  async function freeText(q, isSupport = false) {
    me(q)
    setReplies([])
    setTyping(true)
    const history = msgs.filter((m) => (m.from === 'me' && !m.masked && !m.kind) || m.kind === 'answer').slice(-8)
      .map((m) => ({ role: m.from === 'me' ? 'user' : 'assistant', content: String(m.text).slice(0, 2000) }))
    try {
      const r = await api.chat(q, null, lang, history)
      setTyping(false)
      push({ kind: 'answer', text: r.answer, citations: r.citations, privacy: r.privacy_note })
      const top = r.suggested_services?.[0]
      if (top && (top.confidence === 'high' || top.confidence === 'medium')) {
        setReplies([reply(`📄 ${top.title}`, () => { me(top.title); showService(top.service_id, L.found) }, 'primary'),
          reply(L.other, () => { me(L.other); bot({ text: L.menu }).then(menuReplies) }, 'ghost')])
      } else setReplies([
        ...(isSupport ? [reply(`📞 ${L.stillStuck}`, () => { me(L.helplines); showHelplines() }, 'primary')] : []),
        reply(L.other, () => { me(L.other); bot({ text: L.menu }).then(menuReplies) }, 'ghost')])
    } catch (e) {
      setTyping(false)
      push({ text: `Sorry — ${e.message}`, tone: 'bad' })
    }
  }

  // ---------------------------------------------------------------- conversational form
  async function startForm(s) {
    me(L.prepare)
    form.current = { s, fields: s.form, idx: 0, values: {}, aadhaar: '' }
    await bot([{ text: L.formIntro(s.title) }, { text: L.formPrivacy, tone: 'good' }], 600)
    askField()
  }

  const serverValues = () => Object.fromEntries(Object.entries(form.current.values).filter(([k, v]) => !LOCAL_ONLY.has(k) && v !== '' && v != null))

  async function askField() {
    const F = form.current
    const f = F.fields[F.idx]
    if (!f) return finishForm()
    setMode({ type: 'field', f })
    setMulti([])
    await bot({ text: f.label, lead: true, sub: f.help }, 380)
    const rs = []
    if (f.type === 'select') f.options.forEach((o) => rs.push(reply(o, () => answer(o))))
    if (OPTIONAL.has(f.id)) rs.push(reply(L.skip, () => { me(L.skip); next() }, 'ghost'))
    setReplies(rs)
    setTimeout(() => input.current?.focus(), 50)
  }

  function next() { form.current.idx += 1; askField() }

  async function answer(raw) {
    const F = form.current
    const f = F?.fields[F.idx]  // read from the ref: reply buttons are created before `mode` state updates
    if (!F || !f) return
    const value = Array.isArray(raw) ? raw : String(raw).trim()
    if (!value || (Array.isArray(value) && !value.length)) return

    if (f.type === 'aadhaar') {
      const r = validateAadhaar(value)
      me(r.ok ? `XXXX XXXX ${value.replace(/\D/g, '').slice(-4)} 🔒` : '•••• •••• ••••', { masked: true })
      if (!r.ok) return bot({ text: r.message, tone: 'bad' }, 300)
      F.aadhaar = value
      await bot({ text: '✓ Looks valid — it stays on this phone.', tone: 'good' }, 300)
      return next()
    }

    const shown = Array.isArray(value) ? value.join(', ') : f.type === 'date' && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value.split('-').reverse().join('/') : value
    me(shown)
    F.values[f.id] = value
    let res
    try { res = await api.validate(F.s.id, serverValues()) } catch (e) { return bot({ text: e.message, tone: 'bad' }) }
    const r = res.fields[f.id]
    if (r && !r.ok) {
      delete F.values[f.id]
      return bot({ text: `⚠️ ${r.message}`, tone: 'bad' }, 350)
    }
    if (r?.level === 'warning') {
      await bot({ text: r.message, tone: 'warn' }, 350)
      return setReplies([reply(L.keep, () => { me(L.keep); next() }, 'primary'),
        reply(L.change, () => { me(L.change); delete F.values[f.id]; setReplies([]); input.current?.focus() }, 'ghost')])
    }
    if (r?.message && r.message !== 'OK' && r.message.length < 90) await bot({ text: `✓ ${r.message}`, tone: 'good' }, 250)
    next()
  }

  async function onFile(file) {
    const F = form.current
    const f = F?.fields[F.idx]
    if (!file || !F || !f) return
    const res = await checkImage(file, f.spec || {})
    me('', { kind: 'image', preview: res?.preview, name: file.name })
    F.values[f.id] = file.name
    if (res && !res.ok) {
      await bot({ text: res.issues.join(' '), tone: 'warn' }, 350)
      return setReplies([reply(L.useAnyway, () => { me(L.useAnyway); next() }), reply(L.another, () => fileIn.current?.click(), 'ghost')])
    }
    await bot({ text: `✓ Meets the size rules (${res.kb} KB, ${res.dims}px). It stays on your device.`, tone: 'good' }, 300)
    next()
  }

  async function finishForm() {
    const F = form.current
    setMode({ type: 'free' })
    await bot({ text: L.checking }, 400)
    try {
      const sheet = await api.handoff(F.s.id, serverValues(), lang)
      for (const w of sheet.warnings) push({ text: w.message, tone: 'warn' })
      await bot({ kind: 'handoff', sheet }, 700)
    } catch (e) { return bot({ text: e.message, tone: 'bad' }) }
    setReplies([reply(`💾 ${L.ack}`, () => { me(L.ack); setMode({ type: 'ack', s: F.s }); bot({ text: L.ackAsk }) }, 'primary'),
      reply(L.other, () => { me(L.other); bot({ text: L.menu }).then(menuReplies) }, 'ghost')])
    form.current = null
  }

  function cancelForm() {
    form.current = null
    setMode({ type: 'free' })
    bot({ text: L.cancelled }).then(menuReplies)
  }

  // ---------------------------------------------------------------- input
  async function send(e) {
    e?.preventDefault()
    const v = mode.f?.type === 'multiselect' ? multi : text.trim()
    if (!v || (Array.isArray(v) && !v.length)) return
    setText('')
    if (mode.type === 'field') return answer(v)
    if (mode.type === 'ack') {
      me(v)
      tracker.add({ service_id: mode.s.id, title: mode.s.title, ack: v.slice(0, 30) })
      setMode({ type: 'free' })
      await bot({ text: L.ackSaved, tone: 'good' })
      return menuReplies()
    }
    freeText(v)
  }

  function reset() {
    form.current = null
    setMode({ type: 'free' })
    setMsgs([]); setReplies([])
    greet()
  }

  // ---------------------------------------------------------------- lifecycle & external commands
  useEffect(() => { if (!started.current) { started.current = true; greet() } }, []) // eslint-disable-line
  useEffect(() => {
    if (!command) return
    if (command.type === 'service') { me(cache.current.list[command.id]?.title || 'Tell me about this service'); showService(command.id) }
    if (command.type === 'reset') reset()
    if (command.type === 'ask' && command.text) freeText(command.text, true)
    if (command.type === 'helplines') { me(L.helplines); showHelplines() }
    if (command.type === 'problem') {
      const p = cache.current.problems.find((x) => x.id === command.id)
      if (p) { setReplies([]); pickProblem(p) }
    }
  }, [command]) // eslint-disable-line

  // ---------------------------------------------------------------- render
  const f = mode.type === 'field' ? mode.f : null
  const F = form.current
  const progress = F ? Math.round((F.idx / F.fields.length) * 100) : 0
  let field
  if (f?.type === 'state') {
    field = <select ref={input} value={text} onChange={(e) => setText(e.target.value)} aria-label={f.label}>
      <option value="">Choose your state…</option>{STATES.map((s) => <option key={s}>{s}</option>)}</select>
  } else if (f?.type === 'photo') {
    field = <>
      <button type="button" className="ibtn" onClick={() => fileIn.current?.click()} aria-label="Attach"><Icon name="paperclip" /></button>
      <input readOnly value="" placeholder={`Tap 📎 to attach your ${f.label.toLowerCase()} (JPG)`} onClick={() => fileIn.current?.click()} />
      <input ref={fileIn} type="file" accept="image/jpeg" hidden onChange={(e) => { onFile(e.target.files[0]); e.target.value = '' }} />
    </>
  } else if (f?.type === 'multiselect') {
    field = <input readOnly value={multi.join(', ')} placeholder="Tap the options above, then send" />
  } else {
    field = <>
      {f?.type === 'aadhaar' && <Icon name="lock" size={18} className="lock" />}
      <input ref={input} value={text} onChange={(e) => setText(f?.upper ? e.target.value.toUpperCase() : e.target.value)}
        type={f?.type === 'date' ? 'date' : f?.type === 'aadhaar' ? 'password' : f?.type === 'email' ? 'email' : f?.type === 'tel' ? 'tel' : 'text'}
        inputMode={f?.type === 'aadhaar' || f?.type === 'tel' ? 'numeric' : undefined} autoComplete="off" maxLength={f ? 120 : 1500}
        placeholder={f?.type === 'aadhaar' ? L.aadhaarPh : f ? (f.placeholder || f.label) : L.placeholder} aria-label={f ? f.label : L.placeholder} />
    </>
  }

  return (
    <>
      {header}
      <div className="wall" ref={wall}>
        <div className="thread">
          <span className="day">{lang === 'hi' ? 'आज' : lang === 'te' ? 'ఈరోజు' : 'Today'}</span>
          <div className="sysnote"><Icon name="lock" size={15} /><span>{lang === 'hi'
            ? 'CivicRoute सरकारी वेबसाइट नहीं है। आप आवेदन, हस्ताक्षर और भुगतान स्वयं आधिकारिक पोर्टल पर करते हैं।'
            : 'CivicRoute is not a government website. You apply, sign and pay on the official portal yourself.'}</span></div>
          {msgs.map((m, i) => (
            <Message key={m.id} m={m} same={i > 0 && msgs[i - 1].from === m.from && !msgs[i - 1].kind && !m.kind}
              lang={lang} act={{ steps: (s) => { me(L.steps); showSteps(s) }, prepare: startForm, ask: askAbout }} />
          ))}
          {typing && <Typing />}
          {!typing && f?.type === 'multiselect' && (
            <div className="qr">
              {f.options.map((o) => (
                <button key={o} className={multi.includes(o) ? 'on' : ''} onClick={() => setMulti((m) => (m.includes(o) ? m.filter((x) => x !== o) : [...m, o]))}>
                  {multi.includes(o) && <Icon name="check" size={14} />}{o}</button>
              ))}
              <button className="primary" disabled={!multi.length} onClick={() => answer(multi)}>{L.done} →</button>
            </div>
          )}
          {!typing && replies.length > 0 && (
            <div className="qr">{replies.map((r, i) => <button key={i} className={r.cls} onClick={() => { setReplies([]); r.fn() }}>{r.label}</button>)}</div>
          )}
        </div>
      </div>

      {F && (
        <div className="form-bar">
          <strong>{F.s.title}</strong>
          <span className="prog"><i style={{ width: `${progress}%` }} /></span>
          <span className="muted">{F.idx}/{F.fields.length}</span>
          <button onClick={cancelForm}>Cancel</button>
        </div>
      )}
      <form className="composer" onSubmit={send}>
        <div className="field">{field}</div>
        <button className="cbtn" disabled={typing || (f?.type === 'photo') || (f?.type === 'multiselect' ? !multi.length : !text.trim())} aria-label="Send">
          <Icon name="send" size={20} />
        </button>
      </form>
      <div className="hint">{f
        ? (lang === 'hi' ? '🔒 तुरंत जाँचा जाता है · कहीं सहेजा नहीं जाता · AI को नहीं भेजा जाता' : '🔒 Checked instantly · never saved · never sent to the AI')
        : (lang === 'hi' ? 'चैट में आधार, PAN या OTP न लिखें।' : "Please don't type your Aadhaar, PAN or OTP in chat.")}</div>
    </>
  )
}
