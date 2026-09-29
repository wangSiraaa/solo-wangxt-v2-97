/** Severity-coloured diagnostic/input-check list. */
const STYLE = {
  error: { bg: '#fdecea', border: '#e57373', icon: '⛔', label: '错误' },
  warning: { bg: '#fff7e6', border: '#f0ad4e', icon: '⚠️', label: '注意' },
  info: { bg: '#eef5ff', border: '#6da4e8', icon: 'ℹ️', label: '说明' },
}

export default function Diagnostics({ title, items }) {
  if (!items || items.length === 0) return null
  return (
    <section className="card">
      <h3>{title}</h3>
      <ul className="diag-list">
        {items.map((it, i) => {
          const st = STYLE[it.severity] ?? STYLE.info
          return (
            <li
              key={i}
              style={{ background: st.bg, borderColor: st.border }}
              className="diag-item"
            >
              <span className="diag-badge" style={{ background: st.border }}>
                {st.icon} {st.label}
              </span>
              <code className="diag-code">{it.code}</code>
              <span>{it.message}</span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
