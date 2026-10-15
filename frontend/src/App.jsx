import { useEffect, useRef, useState } from 'react'
import Icon from './components/Icon.jsx'
import Logo, { Wordmark } from './components/Logo.jsx'
import ChatApp from './chat/ChatApp.jsx'
import Home from './pages/Home.jsx'
import ServicePage from './pages/ServicePage.jsx'
import Apply from './pages/Apply.jsx'
import Tracker from './pages/Tracker.jsx'
import Info from './pages/Info.jsx'
import { api } from './lib/api.js'
import { t } from './lib/i18n.js'
import './chat.css'

// Routes: #/  #/services  #/service/<id>  #/apply/<id>  #/track  #/helpdesk  #/updates  #/page/<disclaimer|privacy|accessibility|security>
function parseHash() {
  const [, page = '', id = ''] = (window.location.hash || '#/').split('/')
  return { page: page || 'home', id: decodeURIComponent(id) }
}
const load = (k, d) => { try { return localStorage.getItem(k) || d } catch { return d } }
const save = (k, v) => { try { localStorage.setItem(k, v) } catch { /* private mode */ } }
const SCALES = [['A-', 0.9], ['A', 1], ['A+', 1.12]]
const LANGS = [['en', 'English'], ['hi', 'हिंदी'], ['te', 'తెలుగు']]

export default function App() {
  const [route, setRoute] = useState(parseHash())
  const [lang, setLang] = useState(() => load('civicroute.lang', 'en'))
  const [scale, setScale] = useState(() => Number(load('civicroute.scale', '1')))
  const [contrast, setContrast] = useState(() => load('civicroute.contrast', 'normal'))
  const [theme, setTheme] = useState(() => load('civicroute.theme2', 'light'))
  const [services, setServices] = useState([])
  const [meta, setMeta] = useState(null)
  const [updates, setUpdates] = useState({ updates: [], last_checked: null })
  const [support, setSupport] = useState({ helplines: [] })
  const [dd, setDd] = useState(false)
  const [navOpen, setNavOpen] = useState(false)
  const [paused, setPaused] = useState(false)
  const [hd, setHd] = useState({ open: false, mounted: false })
  const [command, setCommand] = useState(null)
  const ddRef = useRef(null)

  useEffect(() => {
    const onHash = () => { setRoute(parseHash()); setDd(false); setNavOpen(false); window.scrollTo({ top: 0 }) }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  useEffect(() => { save('civicroute.lang', lang); document.documentElement.lang = lang }, [lang])
  useEffect(() => { save('civicroute.scale', String(scale)); document.documentElement.style.setProperty('--scale', scale) }, [scale])
  useEffect(() => {
    save('civicroute.contrast', contrast)
    if (contrast === 'high') document.documentElement.dataset.contrast = 'high'
    else delete document.documentElement.dataset.contrast
  }, [contrast])
  useEffect(() => { save('civicroute.theme2', theme); document.documentElement.dataset.theme = theme }, [theme])
  useEffect(() => { api.meta().then(setMeta).catch(() => {}) }, [])
  useEffect(() => {
    api.services(lang).then(setServices).catch(() => {})
    api.updates(lang).then(setUpdates).catch(() => {})
    api.support(lang).then(setSupport).catch(() => {})
  }, [lang])
  useEffect(() => {
    const close = (e) => { if (ddRef.current && !ddRef.current.contains(e.target)) setDd(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  useEffect(() => { if (route.page === 'helpdesk') openHelp() }, [route.page]) // eslint-disable-line

  function openHelp(cmd) {
    const wasMounted = hd.mounted
    setHd({ open: true, mounted: true })
    if (cmd) setTimeout(() => setCommand({ ...cmd, n: Date.now() }), wasMounted ? 0 : 1100)
  }

  const props = { lang, services, meta, updates, support, openHelp }
  let page
  if (route.page === 'service') page = <ServicePage key={route.id} id={route.id} {...props} />
  else if (route.page === 'apply') page = <Apply key={route.id} id={route.id} {...props} />
  else if (route.page === 'track') page = <Tracker {...props} />
  else if (['page', 'helpdesk', 'services', 'updates'].includes(route.page)) page = <Info kind={route.page === 'page' ? route.id : route.page} {...props} />
  else page = <Home {...props} />

  const on = (p) => (route.page === p ? 'on' : '')
  const tickerItems = updates.updates.slice(0, 6)

  return (
    <>
      <a href="#main" className="skip" onClick={(e) => { e.preventDefault(); document.getElementById('main')?.focus() }}>{t(lang, 'skip')}</a>

      <div className="topstrip" role="region" aria-label="Accessibility tools">
        <div className="wrap">
          <span className="notgov"><Icon name="shield-check" size={15} /><span className="long">{t(lang, 'notgov')} ·</span> <b>{t(lang, 'notgov_b')}</b></span>
          <div className="tools">
            {SCALES.map(([label, v]) => (
              <button key={label} className={scale === v ? 'on' : ''} onClick={() => setScale(v)} aria-label={`Text size ${label}`} aria-pressed={scale === v}>{label}</button>
            ))}
            <span className="sep" />
            <span className="themetoggle" role="group" aria-label="Theme">
              <button className={theme === 'light' ? 'on' : ''} onClick={() => setTheme('light')} aria-pressed={theme === 'light'}><Icon name="sun" size={13} /> <span className="lbl">{t(lang, 'theme_day')}</span></button>
              <button className={theme === 'dark' ? 'on' : ''} onClick={() => setTheme('dark')} aria-pressed={theme === 'dark'}><Icon name="moon" size={13} /> <span className="lbl">{t(lang, 'theme_night')}</span></button>
            </span>
            <button className={`contrast-btn ${contrast === 'high' ? 'on' : ''}`} onClick={() => setContrast(contrast === 'high' ? 'normal' : 'high')} aria-pressed={contrast === 'high'} title="High contrast">
              <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="2" /><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor" /></svg>
              <span className="lbl">{t(lang, 'contrast')}</span></button>
            <span className="sep" />
            <select value={lang} onChange={(e) => setLang(e.target.value)} aria-label="Language">
              {LANGS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
        </div>
      </div>

      <header className="header">
        <div className="wrap">
          <a className="brand" href="#/" aria-label="CivicRoute home">
            <Logo size={56} />
            <Wordmark sub={t(lang, 'brand_sub')} />
          </a>
          <form className="hsearch" role="search" onSubmit={(e) => { e.preventDefault(); const q = e.target.q.value.trim(); if (q) { window.location.hash = '#/'; setTimeout(() => window.dispatchEvent(new CustomEvent('cr-search', { detail: q })), 60) } }}>
            <input name="q" placeholder={t(lang, 'search_ph')} aria-label={t(lang, 'search_ph')} />
            <button aria-label="Search"><Icon name="search" size={18} /></button>
          </form>
          <div className="hbtns">
            <a className="btn" href="#/track"><Icon name="list" size={17} /><span>{t(lang, 'track')}</span></a>
            <button className="btn saffron" onClick={() => openHelp()}><Icon name="sparkles" size={17} /><span>{t(lang, 'support_t')}</span></button>
          </div>
        </div>
      </header>

      <nav className={`mainnav ${navOpen ? 'open' : ''}`} aria-label="Main">
        <div className="wrap">
          <button className="btn sm navtoggle" onClick={() => setNavOpen((o) => !o)} aria-expanded={navOpen}><Icon name="menu" size={18} /> Menu</button>
          <div className="links">
            <a href="#/" className={on('home')}><Icon name="home" size={17} /> {t(lang, 'home')}</a>
            <div className="ddwrap" ref={ddRef}>
              <button className={`dd ${['service', 'apply', 'services'].includes(route.page) ? 'on' : ''}`} onClick={() => setDd((d) => !d)} aria-expanded={dd}>
                {t(lang, 'services')} <Icon name="chevron" size={15} />
              </button>
              {dd && <div className="ddmenu" role="menu">{services.map((s) => <a key={s.id} href={`#/service/${s.id}`}>{s.title}</a>)}</div>}
            </div>
            <a href="#/helpdesk" className={on('helpdesk')}><Icon name="sparkles" size={17} /> {t(lang, 'support')}</a>
            <a href="#/updates" className={on('updates')}><Icon name="info" size={17} /> {t(lang, 'updates')}</a>
            <a href="#/track" className={on('track')}><Icon name="list" size={17} /> {t(lang, 'mine')}</a>
            <a href="#/page/accessibility" className={route.page === 'page' ? 'on' : ''}><Icon name="accessibility" size={17} /> {t(lang, 'accessibility')}</a>
          </div>
        </div>
      </nav>

      <div className={`ticker ${paused ? 'paused' : ''}`} role="region" aria-label={t(lang, 'whatsnew')}>
        <div className="wrap">
          <span className="label">{t(lang, 'whatsnew')}</span>
          <div className="track" aria-live="off"><div className="move">
            {tickerItems.map((u, i) => <span key={i}><a href={u.url} {...(u.url.startsWith('http') ? { target: '_blank', rel: 'noopener noreferrer' } : {})} style={{ color: 'inherit' }}>{u.title}</a></span>)}
          </div></div>
          <button onClick={() => setPaused((p) => !p)} aria-label={paused ? t(lang, 'play') : t(lang, 'pause')}><Icon name={paused ? 'play' : 'pause'} size={13} /></button>
        </div>
      </div>

      <main id="main" tabIndex={-1}>{page}</main>

      <footer className="footer">
        <div className="wrap">
          <div className="cols">
            <div><h4>CivicRoute</h4><p>{t(lang, 'footer_about')}</p></div>
            <div><h4>{t(lang, 'f_services')}</h4>{services.slice(0, 5).map((s) => <a key={s.id} href={`#/service/${s.id}`}>{s.title}</a>)}</div>
            <div>
              <h4>{t(lang, 'f_help')}</h4>
              <a href="#/helpdesk">{t(lang, 'support_t')}</a>
              <a href="#/updates">{t(lang, 'updates')}</a>
              <a href="#/track">{t(lang, 'track')}</a>
              <a href="https://www.incometax.gov.in/iec/foportal/contact-us" target="_blank" rel="noopener noreferrer">{{ en: 'Income Tax helplines', hi: 'आयकर हेल्पलाइन', te: 'ఆదాయపు పన్ను హెల్ప్‌లైన్లు' }[lang]} ↗</a>
            </div>
            <div>
              <h4>{t(lang, 'f_policies')}</h4>
              <a href="#/page/disclaimer">{t(lang, 'disclaimer')}</a>
              <a href="#/page/privacy">{t(lang, 'privacy')}</a>
              <a href="#/page/accessibility">{t(lang, 'accessibility')}</a>
              <a href="#/page/security">{t(lang, 'security')}</a>
            </div>
          </div>
          <div className="base">
            <span>{t(lang, 'disclaimer_short')}</span>
            <span>{t(lang, 'last_checked')}: {updates.last_checked || meta?.last_reviewed || '—'}</span>
          </div>
        </div>
      </footer>

      {!hd.open && (
        <button className="hd-launch" onClick={() => openHelp()} aria-label={t(lang, 'support_t')}>
          <span className="av"><Icon name="sparkles" size={20} /></span>{t(lang, 'support_t')}
        </button>
      )}
      {hd.mounted && (
        <div className="hd-panel" style={{ display: hd.open ? 'block' : 'none' }} role="dialog" aria-label="CivicRoute AI support assistant">
          <div className="hd">
            <ChatApp lang={lang} command={command} support={support} header={(
              <div className="conv-head">
                <span className="logo"><Icon name="sparkles" size={18} /></span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <strong>CivicRoute Support <span className="agent">AI agent</span></strong>
                  <span className="status">{lang === 'te' ? 'ఆన్‌లైన్ · అధికారిక మూలాలు మాత్రమే' : lang === 'hi' ? 'ऑनलाइन · केवल आधिकारिक स्रोत' : 'Online 24×7 · official sources only'}</span>
                </div>
                <button className="hbtn" onClick={() => setCommand({ type: 'reset', n: Date.now() })} aria-label="New conversation" title="New conversation"><Icon name="refresh" size={18} /></button>
                <button className="hbtn" onClick={() => setHd((h) => ({ ...h, open: false }))} aria-label="Minimise"><Icon name="x" size={20} /></button>
              </div>
            )} />
          </div>
        </div>
      )}
    </>
  )
}
