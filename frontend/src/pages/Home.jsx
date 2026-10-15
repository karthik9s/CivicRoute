import { useEffect, useState } from 'react'
import Icon, { isFree, shortFee, tone } from '../components/Icon.jsx'
import { api } from '../lib/api.js'
import { t } from '../lib/i18n.js'

const POPULAR = {
  en: ['Lost my PAN card', 'Surname changed after marriage', 'PAN is inoperative', 'e-PAN not received'],
  hi: ['PAN कार्ड खो गया', 'शादी के बाद नाम बदला', 'PAN निष्क्रिय है', 'e-PAN नहीं मिला'],
  te: ['నా PAN కార్డు పోయింది', 'పెళ్లి తర్వాత ఇంటి పేరు మారింది', 'PAN పనిచేయడం లేదు', 'e-PAN రాలేదు'],
}
const SUPPORT_TOPICS = {
  en: ['Payment done but no update', 'Application rejected', 'Card not delivered', 'Call an official helpline'],
  hi: ['भुगतान हुआ पर अपडेट नहीं', 'आवेदन अस्वीकार हुआ', 'कार्ड नहीं मिला', 'आधिकारिक हेल्पलाइन'],
  te: ['చెల్లించాను కానీ అప్‌డేట్ లేదు', 'దరఖాస్తు తిరస్కరించబడింది', 'కార్డు రాలేదు', 'అధికారిక హెల్ప్‌లైన్'],
}
export const OFFICIAL_LINKS = [
  [{ en: 'Income Tax e-filing portal', hi: 'आयकर ई-फाइलिंग पोर्टल', te: 'ఆదాయపు పన్ను e-ఫైలింగ్ పోర్టల్' }, 'https://www.incometax.gov.in/iec/foportal/'],
  [{ en: 'Instant e-PAN', hi: 'तत्काल e-PAN', te: 'తక్షణ e-PAN' }, 'https://eportal.incometax.gov.in/iec/foservices/#/pre-login/instant-e-pan'],
  [{ en: 'Link Aadhaar with PAN', hi: 'PAN को आधार से लिंक करें', te: 'PAN ను ఆధార్‌తో లింక్ చేయండి' }, 'https://eportal.incometax.gov.in/iec/foservices/#/pre-login/bl-link-aadhaar'],
  [{ en: 'Protean PAN services', hi: 'Protean PAN सेवाएँ', te: 'Protean PAN సేవలు' }, 'https://onlineservices.proteantech.in/paam/endUserRegisterContact.html'],
  [{ en: 'UTIITSL PAN services', hi: 'UTIITSL PAN सेवाएँ', te: 'UTIITSL PAN సేవలు' }, 'https://www.pan.utiitsl.com/'],
  [{ en: 'Track PAN status (Protean)', hi: 'PAN स्थिति ट्रैक करें (Protean)', te: 'PAN స్థితి ట్రాక్ (Protean)' }, 'https://tin.tin.proteantech.in/pantan/StatusTrack.html'],
]
const title = (o, lang, k = 'title') => o[`${k}_${lang}`] || o[k]

export function UpdatesFeed({ lang, updates, height = 300 }) {
  const items = updates.updates
  const row = (u, i, dup) => {
    const d = new Date(u.date || Date.now())
    const ext = u.url.startsWith('http')
    return (
      <a key={`${dup ? 'd' : ''}${i}`} className={`upd ${dup ? 'dup' : ''}`} href={u.url} {...(ext ? { target: '_blank', rel: 'noopener noreferrer' } : {})} tabIndex={dup ? -1 : 0} aria-hidden={dup || undefined}>
        <span className="date"><b>{String(d.getDate()).padStart(2, '0')}</b>{d.toLocaleString('en', { month: 'short' })} {String(d.getFullYear()).slice(2)}</span>
        <span className="t"><span className={`tag ${u.auto ? 'auto' : ''}`}>{u.tag}</span>{u.title}{ext && ' ↗'}</span>
      </a>
    )
  }
  if (!items.length) return <p className="muted small">No updates yet.</p>
  return (
    <>
      <div className="feed" style={{ height }} tabIndex={0} aria-label={t(lang, 'updates')}>
        <div className="feed-track">{items.map((u, i) => row(u, i))}{items.map((u, i) => row(u, i, true))}</div>
      </div>
      <div className="feed-foot"><span><Icon name="clock" size={13} /> {t(lang, 'last_checked')}: {updates.last_checked || '—'}</span><a href="#/updates">{t(lang, 'all_updates')} →</a></div>
    </>
  )
}

export function Helplines({ support, lang = 'en' }) {
  return support.helplines.map((h) => (
    <div key={h.id} className="helpline">
      <b>{h.name}</b>
      <span className="tiny muted">{h.for}</span>
      <div>{h.phones.length ? h.phones.map((p) => <a key={p} className="tel" href={`tel:${p.replace(/[^\d+]/g, '')}`}><Icon name="phone" size={12} /> {p}</a>)
        : <a className="tel" href={h.url} target="_blank" rel="noopener noreferrer">{t(lang, 'contact_details')} ↗</a>}</div>
      <span className="hrs">{h.hours}{h.toll_free && ` · ${t(lang, 'toll_free')}`}</span>
    </div>
  ))
}

export default function Home({ lang, services, updates, support, openHelp }) {
  const [problems, setProblems] = useState([])
  const [q, setQ] = useState('')
  const [asked, setAsked] = useState('')
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => { api.problems().then(setProblems).catch((e) => setErr(e.message)) }, [])
  useEffect(() => {
    const onSearch = (e) => search(e.detail)
    window.addEventListener('cr-search', onSearch)
    return () => window.removeEventListener('cr-search', onSearch)
  }) // eslint-disable-line react-hooks/exhaustive-deps

  async function search(text) {
    const query = (text ?? q).trim()
    if (!query) return
    setQ(query); setAsked(query); setBusy(true); setErr('')
    try { setRes((await api.intent(query, lang)).results) } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  const top = res?.[0]
  const how = ['how1', 'how2', 'how3', 'how4'].map((k) => t(lang, k))

  return (
    <>
      <section className="hero">
        <div className="wrap">
          <div>
            <h1>{t(lang, 'hero_t')}</h1>
            <p className="lead">{t(lang, 'hero_l')}</p>
            <form className="hero-search" onSubmit={(e) => { e.preventDefault(); search() }} role="search">
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t(lang, 'search_ph')} aria-label={t(lang, 'search_ph')} />
              <button disabled={busy}><Icon name="search" size={18} /> {busy ? '…' : t(lang, 'find')}</button>
            </form>
            <div className="try">{t(lang, 'try')} {(POPULAR[lang] || POPULAR.en).map((p) => <button key={p} type="button" onClick={() => search(p)}>{p}</button>)}</div>
            {err && <p className="notice" style={{ marginTop: 14 }}><Icon name="alert" size={18} /> {err}</p>}
            {top && (
              <div className="result" role="status">
                <span className="tiny muted">{t(lang, 'looks')} — “{asked}”</span>
                <a className="go" href={`#/service/${top.service_id}`}>{top.title} <Icon name="arrow-right" size={20} /></a>
                <div className="alt">
                  {res.slice(1).map((r) => <a key={r.service_id} href={`#/service/${r.service_id}`}>{r.title}</a>)}
                  <button className="btn sm" type="button" onClick={() => openHelp({ type: 'ask', text: asked })}><Icon name="sparkles" size={14} /> {t(lang, 'ask')}</button>
                </div>
              </div>
            )}
          </div>
          <aside className="hero-card" aria-label={t(lang, 'how')}>
            <h3>{t(lang, 'how')}</h3>
            <ol>{how.map(([a, b]) => <li key={a}><span><b>{a}</b>{b}</span></li>)}</ol>
          </aside>
        </div>
      </section>

      <div className="wrap page">
        <div className="home-grid">
          <aside className="home-side" aria-label="Quick navigation">
            <div className="panel">
              <div className="panel-head"><Icon name="grid" size={18} /> {t(lang, 'sidebar_services')}</div>
              <div className="panel-body">
                {services.map((s) => (
                  <a key={s.id} className={`item ${tone(s.id)}`} href={`#/service/${s.id}`}>
                    <span className="sq"><Icon name={s.icon} size={15} /></span>{s.title}</a>
                ))}
              </div>
            </div>
            <div className="panel">
              <div className="panel-head"><Icon name="shield-check" size={18} /> {t(lang, 'sidebar_links')}</div>
              <div className="panel-body">
                {OFFICIAL_LINKS.map(([label, url]) => (
                  <a key={url} className="item" href={url} target="_blank" rel="noopener noreferrer" title={t(lang, 'open_new')}>
                    <Icon name="link" size={16} />{label[lang] || label.en}<Icon name="external" size={14} className="ext" /></a>
                ))}
              </div>
            </div>
            <div className="panel">
              <div className="panel-head"><Icon name="phone" size={18} /> {t(lang, 'sidebar_help')}</div>
              <div className="panel-body"><Helplines support={support} lang={lang} />
                <p className="tiny muted" style={{ padding: '4px 8px' }}>{t(lang, 'source')}: <a href="https://www.incometax.gov.in/iec/foportal/contact-us" target="_blank" rel="noopener noreferrer">incometax.gov.in ↗</a></p></div>
            </div>
          </aside>

          <div>
            <section className="support-card">
              <span className="bot"><Icon name="sparkles" size={32} /></span>
              <div>
                <h3>{t(lang, 'support_t')} <span className="agent" style={{ fontSize: '.68rem', background: 'rgba(255,255,255,.2)', padding: '2px 8px', borderRadius: 4, marginLeft: 6 }}>24×7</span></h3>
                <p>{t(lang, 'support_s')}</p>
                <div className="chips">{(SUPPORT_TOPICS[lang] || SUPPORT_TOPICS.en).map((s, i) => (
                  <button key={s} onClick={() => openHelp(i === 3 ? { type: 'helplines' } : { type: 'ask', text: s })}>{s}</button>
                ))}</div>
              </div>
              <button className="btn saffron lg" onClick={() => openHelp()}><Icon name="chat" size={18} /> {t(lang, 'chat_now')}</button>
            </section>

            <section className="section">
              <div className="section-head"><span className="bar" /><div><h2>{t(lang, 'quick')}</h2><p>{t(lang, 'quick_s')}</p></div></div>
              <div className="tiles">
                {services.map((s) => {
                  const fee = shortFee(s.fees, lang)
                  return (
                    <a key={s.id} className={`tile ${tone(s.id)}`} href={`#/service/${s.id}`}>
                      <span className="ico"><Icon name={s.icon} size={26} /></span>
                      <span>{s.title}</span>
                      {fee && <span className={`fee ${isFree(s.fees) ? '' : 'paid'}`}>{fee}</span>}
                    </a>
                  )
                })}
              </div>
            </section>

            <section className="section">
              <div className="section-head"><span className="bar" /><div><h2>{t(lang, 'problems')}</h2><p>{t(lang, 'problems_s')}</p></div></div>
              <div className="problems">
                {problems.map((p) => (
                  <a key={p.id} className={`problem ${tone(p.id)}`} href={p.result ? `#/service/${p.result}` : '#/helpdesk'}
                    onClick={(e) => { if (!p.result) { e.preventDefault(); openHelp({ type: 'problem', id: p.id }) } }}>
                    <Icon name={p.icon} size={20} /> {title(p, lang)} <Icon name="chevron" size={18} />
                  </a>
                ))}
              </div>
            </section>

            <section className="section panel">
              <div className="panel-head"><Icon name="info" size={18} /> {t(lang, 'updates')} <span className="tiny muted" style={{ fontWeight: 500, marginLeft: 'auto' }}>{t(lang, 'updates_s')}</span></div>
              <div className="panel-body"><UpdatesFeed lang={lang} updates={updates} /></div>
            </section>
          </div>
        </div>
      </div>
    </>
  )
}
