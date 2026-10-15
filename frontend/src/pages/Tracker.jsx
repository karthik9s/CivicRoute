import { useState } from 'react'
import Icon from '../components/Icon.jsx'
import { t } from '../lib/i18n.js'
import { tracker } from '../lib/validate.js'

const TRACK_URLS = {
  protean: 'https://tin.tin.proteantech.in/pantan/StatusTrack.html',
  utiitsl: 'https://www.trackpan.utiitsl.com/PANONLINE/forms/TrackPan/trackApp',
  itd: 'https://eportal.incometax.gov.in/iec/foservices/#/pre-login/instant-e-pan',
}
const ITD_SERVICES = new Set(['instant_epan', 'pan_aadhaar_link', 'verify_pan'])

export default function Tracker({ lang }) {
  const [items, setItems] = useState(tracker.list())
  const [ack, setAck] = useState('')
  const [title, setTitle] = useState('PAN application')
  const where = (i) => (ITD_SERVICES.has(i.service_id) ? ['Income Tax portal', TRACK_URLS.itd]
    : /^\d{15}$/.test(i.ack) ? ['Protean (NSDL)', TRACK_URLS.protean] : ['Protean / UTIITSL', TRACK_URLS.protean])

  return (
    <div className="wrap">
      <nav className="crumbs" aria-label="Breadcrumb"><span><a href="#/">{t(lang, 'home')}</a></span><span>{t(lang, 'mine')}</span></nav>
      <div className="page">
        <div className="page-title"><div><h1>{t(lang, 'mine')}</h1>
          <p>{t(lang, 'browser_only')}</p></div></div>

        <section className="panel">
          <div className="panel-head"><Icon name="list" size={18} /> {t(lang, 'saved_apps')}</div>
          <div className="panel-body" style={{ overflowX: 'auto' }}>
            {items.length === 0 ? (
              <p className="muted">{t(lang, 'no_apps')}</p>
            ) : (
              <table className="gtable">
                <thead><tr><th>{t(lang, 'sno')}</th><th>{t(lang, 'application')}</th><th>{t(lang, 'ack_no')}</th><th>{t(lang, 'saved_on')}</th><th>{t(lang, 'track_status')}</th><th /></tr></thead>
                <tbody>{items.map((i, n) => {
                  const [portal, url] = where(i)
                  const days = Math.floor((Date.now() - new Date(i.created)) / 86400000)
                  return (
                    <tr key={i.id}>
                      <td>{n + 1}</td>
                      <td>{i.title}{days > 20 && <div className="tiny" style={{ color: 'var(--red)' }}>{t(lang, 'stuck')}</div>}</td>
                      <td><code>{i.ack}</code></td>
                      <td>{new Date(i.created).toLocaleDateString('en-IN')}</td>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        <a className="btn sm primary" href={url} target="_blank" rel="noopener noreferrer">{portal} ↗</a>{' '}
                        {portal !== 'Income Tax portal' && <a className="btn sm" href={TRACK_URLS.utiitsl} target="_blank" rel="noopener noreferrer">UTIITSL ↗</a>}
                      </td>
                      <td><button className="btn sm" onClick={() => setItems(tracker.remove(i.id))} aria-label="Remove"><Icon name="trash" size={14} /></button></td>
                    </tr>
                  )
                })}</tbody>
              </table>
            )}
          </div>
        </section>

        <section className="fpanel" style={{ marginTop: 20 }}>
          <h3><Icon name="file-plus" size={18} /> {t(lang, 'add_app')}</h3>
          <p className="hint">{t(lang, 'add_app_h')}</p>
          <div className="fgrid">
            <div className="ff"><label htmlFor="tr-title">{t(lang, 'app_for')} <span className="req">*</span></label>
              <input id="tr-title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={80} /></div>
            <div className="ff"><label htmlFor="tr-ack">{t(lang, 'ack_ph')} <span className="req">*</span></label>
              <input id="tr-ack" value={ack} onChange={(e) => setAck(e.target.value)} maxLength={30} /></div>
            <div className="ff" style={{ alignSelf: 'end' }}>
              <button className="btn primary" disabled={!ack.trim()} onClick={() => { setItems(tracker.add({ service_id: 'track_status', title, ack: ack.trim() })); setAck('') }}>
                <Icon name="check" size={16} /> {t(lang, 'save')}</button></div>
          </div>
        </section>
      </div>
    </div>
  )
}
