import { useEffect, useState } from 'react'
import Icon, { shortFee, tone } from '../components/Icon.jsx'
import { api } from '../lib/api.js'
import { t } from '../lib/i18n.js'

const host = (u) => { try { return new URL(u).hostname } catch { return u } }

export default function ServicePage({ id, lang, services, openHelp }) {
  const [s, setS] = useState(null)
  const [tab, setTab] = useState('overview')
  const [err, setErr] = useState('')
  useEffect(() => { api.service(id, lang).then(setS).catch((e) => setErr(e.message)) }, [id, lang])

  const byId = Object.fromEntries(services.map((x) => [x.id, x]))
  if (err) return <div className="wrap page"><p className="notice"><Icon name="alert" size={18} /> {err}</p></div>
  if (!s) return <div className="wrap page"><p className="muted">{t(lang, 'loading')}</p></div>

  const TABS = [['overview', t(lang, 'overview')], ['steps', t(lang, 'steps')], ['documents', t(lang, 'documents')], ['fees', t(lang, 'fees')], ['links', t(lang, 'links')]]
  const portals = [...new Set(s.official_links.map((l) => l.portal))].join(', ')

  return (
    <div className="wrap">
      <nav className="crumbs" aria-label="Breadcrumb"><span><a href="#/">{t(lang, 'home')}</a></span><span><a href="#/services">{t(lang, 'services')}</a></span><span>{s.title}</span></nav>
      <div className="page layout">
        <aside className="side-nav panel" aria-label={t(lang, 'services')}>
          <div className="panel-head"><Icon name="grid" size={18} /> {t(lang, 'services')}</div>
          <div className="panel-body">
            {services.map((x) => (
              <a key={x.id} href={`#/service/${x.id}`} className={`${tone(x.id)} ${x.id === s.id ? 'on' : ''}`}><span className="dot" />{x.title}</a>
            ))}
          </div>
        </aside>

        <div>
          <div className="page-title" style={{ marginBottom: 8 }}>
            <div>
              <h1>{s.title}</h1>
              <p>{s.short}</p>
            </div>
          </div>
          {s.lang && <p className="notice info" style={{ margin: '0 0 12px' }}><Icon name="info" size={18} /> {t(lang, 'machine_note')}</p>}
          <div className="meta-row">
            <span className="chip ok"><Icon name="shield-check" size={14} /> {t(lang, 'verified')}: {s.last_verified}</span>
            <span className="chip fee"><Icon name="wallet" size={14} /> {shortFee(s.fees, lang)}</span>
            <span className="chip"><Icon name="building" size={14} /> {portals}</span>
          </div>

          {s.not_for?.length > 0 && (
            <div className="notice" role="note">
              <Icon name="alert" size={20} />
              <div><b>{t(lang, 'notfor')}:</b>
                <ul style={{ margin: '4px 0 0', paddingLeft: '1.1rem' }}>
                  {s.not_for.map((n, i) => <li key={i}>{n.when} → <a href={`#/service/${n.go_to}`}>{byId[n.go_to]?.title || n.go_to}</a></li>)}
                </ul>
              </div>
            </div>
          )}

          <div className="tabs" role="tablist">
            {TABS.map(([k, label]) => (
              <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{label}</button>
            ))}
          </div>
          <div className="tabpanel" role="tabpanel">
            {tab === 'overview' && (
              <div style={{ display: 'grid', gap: 20 }}>
                <div><h3 style={{ marginBottom: 10 }}>{t(lang, 'eligible')}</h3>
                  <ul className="ul">{s.eligibility.map((e, i) => <li key={i}><Icon name="check" size={16} />{e}</li>)}</ul></div>
                <table className="gtable"><tbody>
                  <tr><th style={{ width: '32%' }}>{t(lang, 'where')}</th><td>{portals}</td></tr>
                  <tr><th>{t(lang, 'time')}</th><td>{s.time}</td></tr>
                  <tr><th>{t(lang, 'fees')}</th><td>{s.fees.map((f) => `${f.label}: ${f.amount}`).join(' · ')}</td></tr>
                </tbody></table>
                {s.common_rejections?.length > 0 && (
                  <div><h3 style={{ marginBottom: 10 }}>{t(lang, 'mistakes')}</h3>
                    <ul className="ul x">{s.common_rejections.map((e, i) => <li key={i}><Icon name="x" size={16} />{e}</li>)}</ul></div>
                )}
                {s.tips?.length > 0 && (
                  <div className="notice info"><Icon name="info" size={20} /><div><b>{t(lang, 'tips')}</b>
                    <ul style={{ margin: '4px 0 0', paddingLeft: '1.1rem' }}>{s.tips.map((e, i) => <li key={i}>{e}</li>)}</ul></div></div>
                )}
              </div>
            )}
            {tab === 'steps' && (
              <ol className="steps">
                {s.steps.map((st, i) => (
                  <li key={i}><span><h3>{st.title}</h3><p>{st.detail}</p>
                    {st.url && <a className="portal" href={st.url} target="_blank" rel="noopener noreferrer"><Icon name="external" size={14} /> {host(st.url)}</a>}</span></li>
                ))}
              </ol>
            )}
            {tab === 'documents' && (
              <table className="gtable"><thead><tr><th style={{ width: 56 }}>{t(lang, 'sno')}</th><th>{t(lang, 'documents')}</th></tr></thead>
                <tbody>{s.documents.map((d, i) => <tr key={i}><td>{i + 1}</td><td>{d}</td></tr>)}</tbody></table>
            )}
            {tab === 'fees' && (
              <>
                <table className="gtable"><thead><tr><th>{t(lang, 'particulars')}</th><th style={{ width: '34%' }}>{t(lang, 'amount')}</th><th style={{ width: '24%' }}>{t(lang, 'fee_src')}</th></tr></thead>
                  <tbody>{s.fees.map((f, i) => (
                    <tr key={i}><td>{f.label}{f.note && <div className="tiny muted">{f.note}</div>}</td><td><b>{f.amount}</b></td>
                      <td>{f.source ? <a href={f.source} target="_blank" rel="noopener noreferrer">{host(f.source)} ↗</a> : <span className="tiny muted">{t(lang, 'shown_on_page')}</span>}</td></tr>
                  ))}</tbody></table>
                <p className="tiny muted" style={{ marginTop: 10 }}>{t(lang, 'fees_note')}</p>
              </>
            )}
            {tab === 'links' && (
              <div className="olinks">
                {s.official_links.map((l) => (
                  <a key={l.url} className="olink" href={l.url} target="_blank" rel="noopener noreferrer">
                    <span><b>{l.label}</b><small>{l.portal} · {host(l.url)}</small></span><Icon name="external" size={18} /></a>
                ))}
              </div>
            )}
          </div>

          <div className="action-bar">
            <a className="btn primary lg" href={`#/apply/${s.id}`}><Icon name="edit" size={18} /> {t(lang, 'prepare')}</a>
            <button className="btn lg" onClick={() => openHelp({ type: 'service', id: s.id })}><Icon name="chat" size={18} /> {t(lang, 'ask')}</button>
          </div>
        </div>
      </div>
    </div>
  )
}
