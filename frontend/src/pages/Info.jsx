import Icon, { shortFee, tone } from '../components/Icon.jsx'
import { t } from '../lib/i18n.js'
import { Helplines } from './Home.jsx'
import { POLICIES } from './policies.js'

export default function Info({ kind, lang, services, updates, support, openHelp }) {
  if (kind === 'updates') {
    return (
      <div className="wrap">
        <nav className="crumbs"><span><a href="#/">{t(lang, 'home')}</a></span><span>{t(lang, 'updates')}</span></nav>
        <div className="page">
          <div className="page-title"><div><h1>{t(lang, 'updates')}</h1><p>{t(lang, 'updates_s')}. {t(lang, 'last_checked')}: <b>{updates.last_checked || '—'}</b></p></div></div>
          <table className="gtable">
            <thead><tr><th style={{ width: 110 }}>{t(lang, 'date')}</th><th style={{ width: 110 }}>{t(lang, 'type')}</th><th>{t(lang, 'update')}</th><th style={{ width: 150 }}>{t(lang, 'official_source')}</th></tr></thead>
            <tbody>{updates.updates.map((u, i) => (
              <tr key={i}><td>{u.date}</td><td><b style={{ color: u.auto ? 'var(--red)' : 'var(--saffron)' }}>{u.tag}</b></td><td>{u.title}</td>
                <td>{u.url.startsWith('http') ? <a href={u.url} target="_blank" rel="noopener noreferrer">{new URL(u.url).hostname} ↗</a> : <a href={u.url}>{t(lang, 'view_service')}</a>}</td></tr>
            ))}</tbody>
          </table>
          <p className="tiny muted" style={{ marginTop: 10 }}>{t(lang, 'auto_rows')}</p>
        </div>
      </div>
    )
  }
  if (kind === 'services') {
    return (
      <div className="wrap">
        <nav className="crumbs"><span><a href="#/">{t(lang, 'home')}</a></span><span>{t(lang, 'services')}</span></nav>
        <div className="page">
          <div className="page-title"><div><h1>{t(lang, 'services')}</h1><p>{t(lang, 'quick_s')}</p></div></div>
          <table className="gtable">
            <thead><tr><th>{t(lang, 'sno')}</th><th>{t(lang, 'service')}</th><th>{t(lang, 'description')}</th><th>{t(lang, 'fee')}</th></tr></thead>
            <tbody>{services.map((s, i) => (
              <tr key={s.id}><td>{i + 1}</td><td><a href={`#/service/${s.id}`}><b>{s.title}</b></a></td><td>{s.short}</td><td style={{ whiteSpace: 'nowrap' }}>{shortFee(s.fees, lang)}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </div>
    )
  }
  if (kind === 'helpdesk') {
    return (
      <div className="wrap">
        <nav className="crumbs"><span><a href="#/">{t(lang, 'home')}</a></span><span>{t(lang, 'support')}</span></nav>
        <div className="page">
          <div className="page-title"><div><h1>{t(lang, 'support_t')}</h1><p>{t(lang, 'support_s')}</p></div>
            <button className="btn saffron lg" onClick={() => openHelp()}><Icon name="sparkles" size={18} /> {t(lang, 'chat_now')}</button></div>
          <div className="split">
            <div className="panel">
              <div className="panel-head"><Icon name="sparkles" size={18} /> {t(lang, 'agent_can')}</div>
              <div className="panel-body">
                <ul className="ul">
                  <li><Icon name="check" size={16} />Find the right PAN service from a description of your problem (English, हिंदी, తెలుగు)</li>
                  <li><Icon name="check" size={16} />Answer questions with citations from official government sources only</li>
                  <li><Icon name="check" size={16} />Prepare your application details one question at a time, with instant checks</li>
                  <li><Icon name="check" size={16} />Help with problems: payment not reflecting, rejection, card not delivered</li>
                  <li><Icon name="check" size={16} />Give you the official helpline when a human is needed</li>
                </ul>
                <p className="notice info" style={{ marginTop: 14 }}><Icon name="lock" size={18} /> {t(lang, 'agent_never')}</p>
              </div>
            </div>
            <div className="panel">
              <div className="panel-head"><Icon name="phone" size={18} /> {t(lang, 'sidebar_help')}</div>
              <div className="panel-body"><Helplines support={support} lang={lang} />
                <p className="tiny muted" style={{ padding: '4px 8px' }}>{t(lang, 'verified_from')} <a href="https://www.incometax.gov.in/iec/foportal/contact-us" target="_blank" rel="noopener noreferrer">incometax.gov.in/contact-us ↗</a></p></div>
            </div>
          </div>
          <div className="section-head section"><span className="bar" /><div><h2>{t(lang, 'ask_about')}</h2></div></div>
          <div className="tiles">
            {services.map((sv) => (
              <button key={sv.id} className={`tile ${tone(sv.id)}`} onClick={() => openHelp({ type: 'service', id: sv.id })}>
                <span className="ico"><Icon name={sv.icon} size={24} /></span><span>{sv.title}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    )
  }
  const page = POLICIES[kind] || POLICIES.disclaimer
  const [title, sections] = page[lang] || page.en
  return (
    <div className="wrap">
      <nav className="crumbs"><span><a href="#/">{t(lang, 'home')}</a></span><span>{title}</span></nav>
      <div className="page">
        <div className="page-title"><h1>{title}</h1></div>
        <div className="prose panel"><div className="panel-body">
          {sections.map(([h, p]) => <section key={h}><h2>{h}</h2><p>{p}</p></section>)}
        </div></div>
      </div>
    </div>
  )
}
