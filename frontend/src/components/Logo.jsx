// CivicRoute mark: a PAN-style ID card with a route that ends in a check — "your route to a correct PAN".
// Deliberately not resembling any government emblem.
export default function Logo({ size = 52, title = 'CivicRoute' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label={title} className="logo-svg">
      <rect x="4" y="12" width="46" height="34" rx="6" fill="var(--logo-card, #1f3c88)" />
      <rect x="4" y="12" width="46" height="8" rx="6" fill="var(--logo-band, #2d4fa8)" />
      <rect x="4" y="17" width="46" height="3" fill="var(--logo-band, #2d4fa8)" />
      <rect x="10" y="25" width="12" height="14" rx="2" fill="#ffffff" opacity=".92" />
      <circle cx="16" cy="30" r="2.6" fill="var(--logo-card, #1f3c88)" />
      <path d="M11.5 38c1-2.6 2.6-3.6 4.5-3.6s3.5 1 4.5 3.6" fill="var(--logo-card, #1f3c88)" />
      <rect x="26" y="26" width="18" height="3" rx="1.5" fill="#ffffff" opacity=".9" />
      <rect x="26" y="32" width="13" height="3" rx="1.5" fill="#ffffff" opacity=".6" />
      <path d="M8 54 C 22 54, 26 44, 38 44 S 50 34, 52 26" fill="none" stroke="#e8711a" strokeWidth="4" strokeLinecap="round" strokeDasharray="0.1 7" />
      <circle cx="8" cy="54" r="3.2" fill="#e8711a" />
      <circle cx="52" cy="20" r="10" fill="#1e8e3e" stroke="var(--logo-ring, #ffffff)" strokeWidth="3" />
      <path d="M47.5 20.2l3 3 6-6.2" fill="none" stroke="#ffffff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function Wordmark({ sub }) {
  return (
    <span className="wordmark">
      <span className="wm-name"><span className="wm-a">Civic</span><span className="wm-b">Route</span></span>
      {sub && <small>{sub}</small>}
    </span>
  )
}
