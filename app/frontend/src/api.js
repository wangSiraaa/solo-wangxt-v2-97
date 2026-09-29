const BASE = ''

async function postJSON(path, body) {
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = data.detail
    throw new Error(
      typeof detail === 'string'
        ? detail
        : JSON.stringify(detail ?? `HTTP ${res.status}`),
    )
  }
  return data
}

async function getJSON(path) {
  const res = await fetch(BASE + path)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return data
}

export const api = {
  fit: (payload) => postJSON('/api/fit', payload),
  runs: () => getJSON('/api/runs'),
  run: (id) => getJSON(`/api/runs/${id}`),
  refit: (id) => postJSON(`/api/runs/${id}/refit`, {}),
  demo: async (kind) => getJSON(`/api/demo/${kind}`),
}

/** Parse loose CSV/TSV text into {t, drawdown} pairs.
 * Empty / NA / null second column -> missing drawdown, kept as null. */
export function parseObservations(text) {
  const rows = []
  const errors = []
  text.split(/\r?\n/).forEach((line, i) => {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) return
    const parts = trimmed.split(/[\t,;\s]+/).filter(Boolean)
    if (parts.length === 0) return
    const isMissingToken = (v) =>
      v === '' || /^(na|n\/a|null|none|缺失|-)$/i.test(v)
    if (parts.length === 1) {
      // Only a time present -> drawdown missing.
      const t = Number(parts[0])
      if (Number.isFinite(t)) rows.push({ t, drawdown: null })
      else errors.push(`第 ${i + 1} 行无法解析：${line}`)
      return
    }
    const [tRaw, dRaw] = parts
    const t = isMissingToken(tRaw) ? null : Number(tRaw)
    const d = isMissingToken(dRaw) ? null : Number(dRaw)
    if ((t !== null && !Number.isFinite(t)) || (d !== null && !Number.isFinite(d))) {
      errors.push(`第 ${i + 1} 行含非数值：${line}`)
      return
    }
    rows.push({ t, drawdown: d })
  })
  return { rows, errors }
}
