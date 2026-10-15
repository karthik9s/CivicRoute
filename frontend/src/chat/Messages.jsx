import { useState } from 'react'
import Icon, { isFree, shortFee, tone } from '../components/Icon.jsx'
import { t as tr } from '../lib/i18n.js'

const host = (u) => { try { return new URL(u).hostname } catch { return u } }

function Time({ t, me }) {
  return <span className="time">{t}{me && <Icon name="ticks" size={15} className="ticks" />}</span>
}

// [n] -> citation link, **x** -> bold
function RichText({ text, citations = [] }) {
  const parts = text.split(/(\[\d+\]|\*\*[^*]+\*\*)/g)
  return (
    <p className="answer">{parts.map((p, i) => {
      const c = p.match(/^\[(\d+)\]$/)
      if (c) {
        const src = citations[+c[1] - 1]
        return src ? <a key={i} className="cite" href={src.url} target="_blank" rel="noopener noreferrer" title={src.title}>{c[1]}</a> : null
      }
      const b = p.match(/^\*\*([^*]+)\*\*$/)
      return b ? <strong key={i}>{b[1]}</strong> : <span key={i}>{p}</span>
    })}</p>
  )
}

function ServiceCard({ s, t, act, lang }) {
  const fee = shortFee(s.fees, lang)
  return (
    <div className={`b card ${tone(s.id)}`}>
      <div className="card-head">
        <span className="card-ico"><Icon name={s.icon} size={22} /></span>
        <span className="grow"><strong>{s.title}</strong><span className="small muted">{s.short}</span></span>
      </div>
      <div className="facts">
        {fee && <span className={`pill ${isFree(s.fees) ? 'free' : 'fee'}`}><Icon name="wallet" size={13} /> {fee}</span>}
        <span className="pill"><Icon name="building" size={13} /> {[...new Set(s.official_links.map((l) => l.portal))].join(' · ')}</span>
        <span className="pill verified"><Icon name="shield-check" size={13} /> {s.last_verified}</span>
      </div>
      <div className="card-actions">
        <button onClick={() => act.steps(s)}><Icon name="list" size={16} /> {tr(lang, 'steps_btn')}</button>
        <button onClick={() => act.prepare(s)}><Icon name="edit" size={16} /> {tr(lang, 'prepare_btn')}</button>
        <button onClick={() => act.ask(s)}><Icon name="chat" size={16} /> {tr(lang, 'ask_btn')}</button>
      </div>
      <Time t={t} />
    </div>
  )
}

function StepsCard({ s, t, lang }) {
  return (
    <div className={`b card ${tone(s.id)}`}>
      <div className="card-head">
        <span className="card-ico"><Icon name="route" size={22} /></span>
        <span className="grow"><strong>{tr(lang, 'how_to')}: {s.title}</strong><span className="small muted">{s.steps.length} {tr(lang, 'from_official')}</span></span>
      </div>
      <div className="card-sec"><ol className="steps">{s.steps.map((st, i) => (
        <li key={i}><span><strong>{st.title}</strong><p>{st.detail}</p>
          {st.url && <a href={st.url} target="_blank" rel="noopener noreferrer">{host(st.url)} ↗</a>}</span></li>
      ))}</ol></div>
      <div className="card-sec"><h4>{tr(lang, 'keep_ready')}</h4>
        <ul className="ul">{s.documents.map((d, i) => <li key={i}><Icon name="check" size={14} />{d}</li>)}</ul></div>
      <div className="card-sec"><h4>{tr(lang, 'fees')}</h4>
        {s.fees.map((f, i) => (
          <div key={i} className="feeline"><span>{f.label}{f.source && <a href={f.source} target="_blank" rel="noopener noreferrer">{tr(lang, 'source')}: {host(f.source)} ↗</a>}</span><strong>{f.amount}</strong></div>
        ))}</div>
      {s.common_rejections?.length > 0 && (
        <div className="card-sec"><h4>{tr(lang, 'avoid')}</h4>
          <ul className="ul x">{s.common_rejections.map((d, i) => <li key={i}><Icon name="x" size={14} />{d}</li>)}</ul></div>
      )}
      {s.tips?.length > 0 && (
        <div className="card-sec"><h4>{tr(lang, 'tips')}</h4>
          <ul className="ul tip">{s.tips.map((d, i) => <li key={i}><Icon name="sparkles" size={14} />{d}</li>)}</ul></div>
      )}
      <div className="card-sec"><h4>{tr(lang, 'links')}</h4>
        {s.official_links.map((l) => (
          <a key={l.url} className="olink" href={l.url} target="_blank" rel="noopener noreferrer">
            <span>{l.label}<small>{host(l.url)}</small></span><Icon name="external" size={16} /></a>
        ))}</div>
      <Time t={t} />
    </div>
  )
}

function HandoffCard({ sheet, t, lang }) {
  const [copied, setCopied] = useState(null)
  const copy = async (k, v) => {
    try { await navigator.clipboard.writeText(String(v).split('  →')[0]); setCopied(k); setTimeout(() => setCopied(null), 1500) } catch { /* ignore */ }
  }
  return (
    <div className="b card">
      <div className="banner">
        <span className="card-ico"><Icon name="check" size={24} stroke={2.6} /></span>
        <span><strong className="block">{tr(lang, 'ready_t')}</strong><span className="small">{tr(lang, 'ready_s')}</span></span>
      </div>
      <div className="card-sec"><h4>1 · {tr(lang, 'h1_open')}</h4>
        {sheet.official_links.map((l) => (
          <a key={l.url} className="olink" href={l.url} target="_blank" rel="noopener noreferrer">
            <span>{l.label}<small>{host(l.url)}</small></span><Icon name="external" size={16} /></a>
        ))}</div>
      <div className="card-sec"><h4>2 · {tr(lang, 'h2_fill')}</h4>
        {sheet.rows.map((r) => (
          <div key={r.field} className="sheet-row">
            <span className="grow"><span className="k block">{r.portal_label}</span><span className="v">{r.value}</span></span>
            {!/yourself|Upload/.test(r.value) && <button className={`copy ${copied === r.field ? 'done' : ''}`} onClick={() => copy(r.field, r.value)}>{copied === r.field ? tr(lang, 'copied') : tr(lang, 'copy')}</button>}
          </div>
        ))}</div>
      <div className="card-sec"><h4>3 · {tr(lang, 'h3_keep')}</h4>
        <ul className="ul">{sheet.checklist.map((c, i) => <li key={i}><Icon name="check" size={14} />{c}</li>)}</ul></div>
      <div className="card-sec"><h4>4 · {tr(lang, 'h4_pay')}</h4>
        {sheet.fees.map((f, i) => <div key={i} className="feeline"><span>{f.label}</span><strong>{f.amount}</strong></div>)}
        <ul className="ul" style={{ marginTop: 8 }}>{sheet.safety.map((c, i) => <li key={i}><Icon name="shield-check" size={14} />{c}</li>)}</ul></div>
      <Time t={t} />
    </div>
  )
}

function HelplineCard({ lines, t, lang }) {
  return (
    <div className="b card">
      <div className="card-head">
        <span className="card-ico"><Icon name="phone" size={22} /></span>
        <span className="grow"><strong>{tr(lang, 'helplines_t')}</strong><span className="small muted">{tr(lang, 'verified_from')}: incometax.gov.in/contact-us</span></span>
      </div>
      {lines.map((h) => (
        <div key={h.id} className="hl">
          <b>{h.name}</b><span className="for">{h.for}</span>
          <div>{h.phones.length ? h.phones.map((p) => <a key={p} className="tel" href={`tel:${p.replace(/[^\d+]/g, '')}`}><Icon name="phone" size={13} /> {p}</a>)
            : <a className="tel" href={h.url} target="_blank" rel="noopener noreferrer">{tr(lang, 'contact_details')} ↗</a>}</div>
          <span className="hrs">{h.hours}{h.toll_free ? ` · ${tr(lang, 'toll_free')}` : ''}</span>
        </div>
      ))}
      <Time t={t} />
    </div>
  )
}

export function Message({ m, same, act, lang = 'en' }) {
  const me = m.from === 'me'
  let body
  if (m.kind === 'helpline') body = <HelplineCard lines={m.lines} t={m.t} lang={lang} />
  else if (m.kind === 'service') body = <ServiceCard s={m.s} t={m.t} act={act} lang={lang} />
  else if (m.kind === 'steps') body = <StepsCard s={m.s} t={m.t} lang={lang} />
  else if (m.kind === 'handoff') body = <HandoffCard sheet={m.sheet} t={m.t} lang={lang} />
  else if (m.kind === 'image') {
    body = <div className="b">{m.preview && <img className="preview-img" src={m.preview} alt="" />}<span className="small">{m.name}</span><Time t={m.t} me /></div>
  } else if (m.kind === 'answer') {
    body = (
      <div className="b">
        {m.privacy && <p className="small" style={{ color: 'var(--warn)', marginBottom: 6 }}><Icon name="lock" size={13} /> {m.privacy}</p>}
        <RichText text={m.text} citations={m.citations} />
        {m.citations?.length > 0 && (
          <details className="sources"><summary>{tr(lang, 'sources')} ({m.citations.length})</summary>
            <ol>{m.citations.map((c) => <li key={c.n}><a href={c.url} target="_blank" rel="noopener noreferrer">{c.title}</a> <span className="muted">· {c.portal}</span></li>)}</ol>
          </details>
        )}
        <Time t={m.t} />
      </div>
    )
  } else {
    body = (
      <div className={`b ${m.tone || ''}`}>
        <p className={m.lead ? 'lead' : ''}>{m.masked ? <span className="masked">{m.text}</span> : m.text}</p>
        {m.sub && <p className="small" style={{ opacity: .8 }}>{m.sub}</p>}
        <Time t={m.t} me={me} />
      </div>
    )
  }
  return <div className={`m ${me ? 'me' : 'bot'} ${same ? 'same' : ''}`}>{body}</div>
}

export function Typing() {
  return <div className="m bot"><div className="b"><span className="typing"><i /><i /><i /></span></div></div>
}
