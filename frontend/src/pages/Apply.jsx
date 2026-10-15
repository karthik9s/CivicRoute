import { useEffect, useMemo, useState } from 'react'
import Icon from '../components/Icon.jsx'
import { api } from '../lib/api.js'
import { t } from '../lib/i18n.js'
import { checkImage, tracker, validateAadhaar } from '../lib/validate.js'

const GROUPS = [
  { id: 'applicant', title: 'g_applicant', hint: 'g_applicant_h', icon: 'user-plus',
    fields: ['pan', 'change_fields', 'full_name', 'proof_name', 'name_on_card', 'father_name', 'mother_name', 'dob', 'gender', 'aadhaar_local', 'other_pans', 'ack_number'] },
  { id: 'contact', title: 'g_contact', hint: 'g_contact_h', icon: 'home',
    fields: ['mobile', 'email', 'address_line1', 'address_line2', 'city', 'state', 'pincode'] },
  { id: 'documents', title: 'g_docs', hint: 'g_docs_h', icon: 'file',
    fields: ['photo', 'signature', 'proofs'] },
]
const OPTIONAL = new Set(['mother_name', 'address_line2', 'proof_name', 'other_pans', 'photo', 'signature'])
const LOCAL_ONLY = new Set(['aadhaar_local', 'photo', 'signature'])
const WIDE = new Set(['change_fields', 'proofs', 'address_line1', 'address_line2', 'photo', 'signature'])
const STATES = ['Andaman and Nicobar Islands', 'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chandigarh', 'Chhattisgarh',
  'Dadra and Nagar Haveli and Daman and Diu', 'Delhi', 'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jammu and Kashmir', 'Jharkhand',
  'Karnataka', 'Kerala', 'Ladakh', 'Lakshadweep', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha',
  'Puducherry', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal']

export default function Apply({ id, lang }) {
  const [svc, setSvc] = useState(null)
  const [step, setStep] = useState(0)
  const [values, setValues] = useState({})
  const [aadhaar, setAadhaar] = useState('')   // never leaves this component
  const [files, setFiles] = useState({})
  const [checks, setChecks] = useState({})
  const [cross, setCross] = useState([])
  const [sheet, setSheet] = useState(null)
  const [err, setErr] = useState('')
  const [copied, setCopied] = useState(null)
  const [ack, setAck] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => { api.service(id, lang).then(setSvc).catch((e) => setErr(e.message)) }, [id, lang])
  const fieldsById = useMemo(() => Object.fromEntries((svc?.form || []).map((f) => [f.id, f])), [svc])
  const groups = useMemo(() => GROUPS.map((g) => ({ ...g, title: t(lang, g.title), hint: t(lang, g.hint), fields: g.fields.filter((f) => fieldsById[f]) })).filter((g) => g.fields.length), [fieldsById, lang])
  const pages = [...groups.map((g) => ({ id: g.id, title: g.title })), { id: 'review', title: t(lang, 'review') }, { id: 'summary', title: t(lang, 'summary') }]
  const page = pages[step]
  const group = groups.find((g) => g.id === page?.id)

  const serverValues = () => Object.fromEntries(Object.entries(values).filter(([k, v]) => !LOCAL_ONLY.has(k) && v !== '' && v != null && (!Array.isArray(v) || v.length)))
  const set = (k, v) => setValues((s) => ({ ...s, [k]: v }))

  async function validate(ids) {
    const res = await api.validate(id, serverValues())
    const next = { ...checks }
    ids.forEach((f) => { if (res.fields[f]) next[f] = res.fields[f] })
    if (ids.includes('aadhaar_local')) next.aadhaar_local = aadhaar ? validateAadhaar(aadhaar) : null
    setChecks(next); setCross(res.cross_checks)
    return next
  }

  async function saveNext() {
    setErr('')
    if (group) {
      let res
      try { res = await validate(group.fields) } catch (e) { return setErr(e.message) }
      const missing = group.fields.filter((f) => !OPTIONAL.has(f) && (f === 'aadhaar_local' ? !(aadhaar && validateAadhaar(aadhaar).ok)
        : (!values[f] || (Array.isArray(values[f]) && !values[f].length) || (res[f] && !res[f].ok))))
      if (missing.length) return setErr(`${t(lang, 'fix_fields')} ${missing.map((f) => fieldsById[f]?.label || f).join(', ')}`)
    }
    if (pages[step + 1]?.id === 'summary') {
      try { setSheet(await api.handoff(id, serverValues(), lang)) } catch (e) { return setErr(e.message) }
    }
    setStep((s) => s + 1); window.scrollTo({ top: 0 })
  }

  async function onFile(k, file) {
    const r = await checkImage(file, fieldsById[k].spec || {})
    setFiles((f) => ({ ...f, [k]: r })); set(k, file ? file.name : '')
  }
  const copy = async (k, v) => { try { await navigator.clipboard.writeText(String(v).split('  →')[0]); setCopied(k); setTimeout(() => setCopied(null), 1500) } catch { /* ignore */ } }

  if (!svc) return <div className="wrap page">{err ? <p className="notice"><Icon name="alert" size={18} /> {err}</p> : <p className="muted">{t(lang, 'loading')}</p>}</div>

  return (
    <div className="wrap">
      <nav className="crumbs" aria-label="Breadcrumb"><span><a href="#/">{t(lang, 'home')}</a></span><span><a href={`#/service/${svc.id}`}>{svc.title}</a></span><span>{t(lang, 'prepare')}</span></nav>
      <div className="page">
        <div className="page-title"><div><h1>{t(lang, 'prepare')}: {svc.title}</h1>
          <p>{t(lang, 'mandatory')}</p></div></div>

        <ol className="stepper">{pages.map((p, i) => <li key={p.id} className={i === step ? 'on' : i < step ? 'done' : ''}>{p.title}</li>)}</ol>
        {page.id !== 'summary' && <p className="privacy"><Icon name="lock" size={17} /> {t(lang, 'privacy_note')}</p>}

        {group && (
          <section className="fpanel">
            <h3><Icon name={group.icon} size={20} /> {group.title}</h3>
            <p className="hint">{group.hint}</p>
            <div className="fgrid">
              {group.fields.map((fid) => (
                <Field key={fid} lang={lang} f={fieldsById[fid]} wide={WIDE.has(fid)} optional={OPTIONAL.has(fid)} check={checks[fid]} file={files[fid]}
                  value={fid === 'aadhaar_local' ? aadhaar : values[fid]} hints={svc.change_proof_hints}
                  onChange={(v) => (fid === 'aadhaar_local' ? setAadhaar(v) : set(fid, v))}
                  onBlur={() => (fid === 'aadhaar_local' ? setChecks((c) => ({ ...c, aadhaar_local: aadhaar ? validateAadhaar(aadhaar) : null })) : values[fid] && validate([fid]).catch(() => {}))}
                  onFile={(file) => onFile(fid, file)} />
              ))}
            </div>
          </section>
        )}

        {page.id === 'review' && (
          <section className="panel">
            <div className="panel-head"><Icon name="shield-check" size={18} /> {t(lang, 'verify_before')}</div>
            <div className="panel-body" style={{ display: 'grid', gap: 12 }}>
              {cross.length === 0 ? <p className="notice info" style={{ color: 'var(--green)' }}><Icon name="check" size={18} /> {t(lang, 'no_problems')}</p>
                : cross.map((c, i) => <p key={i} className="notice"><Icon name="alert" size={18} /> {c.message}</p>)}
              <table className="gtable"><tbody>
                {Object.entries(values).filter(([, v]) => v && (!Array.isArray(v) || v.length)).map(([k, v]) => (
                  <tr key={k}><th style={{ width: '38%' }}>{fieldsById[k]?.label || k}</th>
                    <td>{Array.isArray(v) ? v.join(', ') : k === 'dob' && /^\d{4}-\d{2}-\d{2}$/.test(v) ? v.split('-').reverse().join('/') : v}</td></tr>
                ))}
                {aadhaar && <tr><th>Aadhaar</th><td>XXXX XXXX {aadhaar.replace(/\D/g, '').slice(-4)} <span className="tiny muted">({t(lang, 'kept_device')})</span></td></tr>}
              </tbody></table>
            </div>
          </section>
        )}

        {page.id === 'summary' && sheet && (
          <section className="ack" aria-label="Application summary">
            <div className="ack-head">
              <span className="tick"><Icon name="check" size={26} stroke={3} /></span>
              <div><h2 style={{ color: '#fff' }}>{t(lang, 'details_ready')}</h2>
                <p style={{ color: '#d8e1fb' }}>{svc.title} · {new Date().toLocaleDateString('en-IN')} · {t(lang, 'not_application')}</p></div>
            </div>
            <div className="ack-body">
              {sheet.warnings.map((w, i) => <p key={i} className="notice"><Icon name="alert" size={18} /> {w.message}</p>)}
              <div>
                <h3 style={{ marginBottom: 8 }}>1. {t(lang, 'h1_open')}</h3>
                <div className="olinks">{sheet.official_links.map((l) => (
                  <a key={l.url} className="olink" href={l.url} target="_blank" rel="noopener noreferrer"><span><b>{l.label}</b><small>{l.portal}</small></span><Icon name="external" size={18} /></a>
                ))}</div>
              </div>
              <div>
                <h3 style={{ marginBottom: 8 }}>2. {t(lang, 'enter_these')}</h3>
                <table className="gtable"><thead><tr><th>{t(lang, 'field_official')}</th><th>{t(lang, 'your_entry')}</th><th style={{ width: 90 }} /></tr></thead>
                  <tbody>{sheet.rows.map((r) => (
                    <tr key={r.field}><td>{r.portal_label}</td><td><b>{r.value}</b></td>
                      <td>{!/yourself|Upload/.test(r.value) && <button className={`copybtn ${copied === r.field ? 'done' : ''}`} onClick={() => copy(r.field, r.value)}>{copied === r.field ? t(lang, 'copied') : t(lang, 'copy')}</button>}</td></tr>
                  ))}</tbody></table>
              </div>
              <div className="split">
                <div><h3 style={{ marginBottom: 8 }}>3. {t(lang, 'h3_keep')}</h3>
                  <ul className="ul">{sheet.checklist.map((c, i) => <li key={i}><Icon name="check" size={16} />{c}</li>)}</ul></div>
                <div><h3 style={{ marginBottom: 8 }}>4. {t(lang, 'fees_pay')}</h3>
                  <table className="gtable"><tbody>{sheet.fees.map((f, i) => <tr key={i}><td>{f.label}</td><td><b>{f.amount}</b></td></tr>)}</tbody></table></div>
              </div>
              <div className="notice info"><Icon name="shield-check" size={20} /><ul style={{ margin: 0, paddingLeft: '1.1rem' }}>{sheet.safety.map((c, i) => <li key={i}>{c}</li>)}</ul></div>
              <div className="fpanel">
                <h3><Icon name="list" size={18} /> {t(lang, 'save_ack_t')}</h3>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 10 }} className="ff">
                  <input value={ack} onChange={(e) => setAck(e.target.value)} placeholder={t(lang, 'ack_ph')} maxLength={30} style={{ flex: '1 1 220px', width: 'auto' }} />
                  <button className="btn primary" disabled={!ack.trim() || saved} onClick={() => { tracker.add({ service_id: svc.id, title: svc.title, ack: ack.trim() }); setSaved(true) }}>
                    {saved ? t(lang, 'saved') : t(lang, 'save_track')}</button>
                </div>
                <p className="tiny muted" style={{ marginTop: 8 }}>{t(lang, 'browser_only')} → “{t(lang, 'mine')}”</p>
              </div>
              <div className="action-bar" style={{ marginTop: 0 }}>
                <button className="btn primary" onClick={() => window.print()}><Icon name="printer" size={17} /> {t(lang, 'print')}</button>
                <a className="btn" href={`#/service/${svc.id}`}><Icon name="back" size={17} /> {t(lang, 'back_service')}</a>
              </div>
            </div>
          </section>
        )}

        {err && <p className="notice" style={{ marginTop: 16 }} role="alert"><Icon name="alert" size={18} /> {err}</p>}
        {page.id !== 'summary' && (
          <div className="form-actions">
            <button className="btn" onClick={() => (step ? setStep(step - 1) : window.history.back())}><Icon name="back" size={16} /> {t(lang, 'back')}</button>
            <button className="btn primary lg" onClick={saveNext}>{pages[step + 1]?.id === 'summary' ? t(lang, 'finish') : t(lang, 'next')} <Icon name="arrow-right" size={17} /></button>
          </div>
        )}
      </div>
    </div>
  )
}

function Field({ f, wide, optional, value, check, file, onChange, onBlur, onFile, hints, lang }) {
  const fid = `f-${f.id}`
  const bad = check && !check.ok
  let input
  if (f.type === 'select' || f.type === 'state') {
    input = <select id={fid} value={value || ''} onChange={(e) => onChange(e.target.value)} onBlur={onBlur}>
      <option value="">{t(lang, 'please_select')}</option>{(f.type === 'state' ? STATES : f.options).map((o) => <option key={o}>{o}</option>)}</select>
  } else if (f.type === 'multiselect') {
    const sel = value || []
    input = <div className="checks">{f.options.map((o) => (
      <label key={o}><input type="checkbox" checked={sel.includes(o)} onChange={() => onChange(sel.includes(o) ? sel.filter((x) => x !== o) : [...sel, o])} /> {o}</label>
    ))}</div>
  } else if (f.type === 'photo') {
    input = <div className="filebox">
      <input id={fid} type="file" accept="image/jpeg" onChange={(e) => onFile(e.target.files[0])} />
      {file && <div style={{ marginTop: 10, overflow: 'hidden' }}>{file.preview && <img src={file.preview} alt="" />}
        {file.ok ? <p className="msg info"><Icon name="check" size={14} /> Meets the specification ({file.kb} KB, {file.dims}px)</p>
          : file.issues.map((x, i) => <p key={i} className="msg error"><Icon name="x" size={14} /> {x}</p>)}</div>}
    </div>
  } else {
    input = <input id={fid} value={value || ''} onBlur={onBlur} placeholder={f.placeholder}
      type={f.type === 'date' ? 'date' : f.type === 'aadhaar' ? 'password' : f.type === 'tel' ? 'tel' : f.type === 'email' ? 'email' : 'text'}
      inputMode={f.type === 'aadhaar' || f.type === 'tel' ? 'numeric' : undefined} autoComplete={f.type === 'aadhaar' ? 'off' : undefined} maxLength={120}
      onChange={(e) => onChange(f.upper ? e.target.value.toUpperCase() : e.target.value)} />
  }
  return (
    <div className={`ff ${wide ? 'full' : ''} ${bad ? 'bad' : ''}`}>
      <label htmlFor={fid}>{f.label}{!optional && <span className="req"> *</span>}</label>
      {input}
      {f.help && <p className="help">{f.help}</p>}
      {f.id === 'change_fields' && (value || []).filter((c) => hints?.[c]).map((c) => <p key={c} className="help">Proof for {c}: {hints[c]}</p>)}
      {check?.message && check.message !== 'OK' && (
        <p className={`msg ${check.ok ? check.level : 'error'}`}><Icon name={check.ok ? (check.level === 'warning' ? 'alert' : 'check') : 'x'} size={14} /> {check.message}</p>
      )}
    </div>
  )
}
