import { useState } from 'react'
import { api, parseObservations } from './api.js'
import ResultsView from './components/ResultsView.jsx'

const DEMO_BOUNDS = {
  t_min_m2_s: 1e-9,
  t_max_m2_s: 1e1,
  s_min: 1e-8,
  s_max: 1e-1,
}

const blankForm = {
  project_name: '',
  distance: '',
  distance_unit: 'm',
  rate: '',
  rate_unit: 'm3/h',
  time_unit: 'min',
  head_unit: 'm',
  static_water_level: '',
  level_datum: 'above_msl',
  datum_note: '',
  observations: [],
  bounds: { ...DEMO_BOUNDS },
  save: true,
}

export default function App() {
  const [form, setForm] = useState(blankForm)
  const [rawText, setRawText] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [runs, setRuns] = useState([])
  const [activeDemo, setActiveDemo] = useState('')

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))
  const setBound = (k, v) =>
    setForm((f) => ({ ...f, bounds: { ...f.bounds, [k]: v } }))

  const ingestText = (text) => {
    const { rows, errors } = parseObservations(text)
    setRawText(text)
    setForm((f) => ({ ...f, observations: rows }))
    setError(errors.length ? errors.join('；') : '')
  }

  const onFile = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const text = await file.text()
    ingestText(text)
    setActiveDemo('')
    e.target.value = ''
  }

  const loadDemo = async (kind) => {
    setBusy(true)
    setError('')
    try {
      const d = await api.demo(kind)
      setForm((f) => ({
        ...f,
        project_name:
          kind === 'clean'
            ? '核对1：合成已知参数'
            : kind === 'noisy'
              ? '核对2：含噪声与缺测'
              : '核对3：距离单位错误',
        distance: d.distance,
        distance_unit: d.distance_unit,
        rate: d.rate,
        rate_unit: d.rate_unit,
        time_unit: d.time_unit,
        head_unit: d.head_unit,
        static_water_level: d.static_water_level ?? '',
        observations: d.observations,
        bounds: { ...DEMO_BOUNDS },
      }))
      setRawText(
        d.observations
          .map((o) => `${o.t}\t${o.drawdown === null ? 'NA' : o.drawdown.toFixed(4)}`)
          .join('\n'),
      )
      setActiveDemo(kind)
      setResult(null)
    } catch (err) {
      setError(String(err))
    } finally {
      setBusy(false)
    }
  }

  const payloadFromForm = () => ({
    project_name: form.project_name || '未命名试验',
    distance: Number(form.distance),
    distance_unit: form.distance_unit,
    rate: Number(form.rate),
    rate_unit: form.rate_unit,
    time_unit: form.time_unit,
    head_unit: form.head_unit,
    static_water_level:
      form.static_water_level === '' ? null : Number(form.static_water_level),
    level_datum: form.level_datum,
    datum_note: form.datum_note || null,
    observations: form.observations,
    bounds: {
      t_min_m2_s: Number(form.bounds.t_min_m2_s),
      t_max_m2_s: Number(form.bounds.t_max_m2_s),
      s_min: Number(form.bounds.s_min),
      s_max: Number(form.bounds.s_max),
    },
    save: form.save,
  })

  const runFit = async () => {
    setBusy(true)
    setError('')
    try {
      const r = await api.fit(payloadFromForm())
      setResult(r)
      if (form.save) refreshRuns()
    } catch (err) {
      setError(String(err))
    } finally {
      setBusy(false)
    }
  }

  const refreshRuns = async () => {
    try {
      setRuns(await api.runs())
    } catch {
      /* list is optional */
    }
  }

  const loadRun = async (id, refit = false) => {
    setBusy(true)
    setError('')
    try {
      const r = refit ? await api.refit(id) : await api.run(id)
      setResult(r)
    } catch (err) {
      setError(String(err))
    } finally {
      setBusy(false)
    }
  }

  const validCount = form.observations.filter(
    (o) => o.t !== null && o.drawdown !== null,
  ).length
  const missCount = form.observations.length - validCount

  return (
    <div className="app">
      <header>
        <h1>抽水试验降深曲线复核</h1>
        <p className="subtitle">
          Theis (1935) 模型 · 均质承压含水层 · 恒定流量 · 单一观测井
        </p>
        <p className="scope-note">
          室内复核辅助工具：基于明确简化模型。不输出真实开采许可；当含水层不满足
          均质承压、无越流、无边界、完整井定流量等假设时，请以结果页的局限提示为准。
        </p>
      </header>

      <div className="layout">
        <div className="left">
          <section className="card">
            <h3>① 井距与抽水量</h3>
            <div className="grid2">
              <label>
                抽水井—观测井距离
                <div className="with-unit">
                  <input
                    type="number"
                    value={form.distance}
                    onChange={(e) => set('distance', e.target.value)}
                  />
                  <select
                    value={form.distance_unit}
                    onChange={(e) => set('distance_unit', e.target.value)}
                  >
                    <option value="m">m</option>
                    <option value="ft">ft</option>
                  </select>
                </div>
              </label>
              <label>
                恒定抽水量 Q
                <div className="with-unit">
                  <input
                    type="number"
                    value={form.rate}
                    onChange={(e) => set('rate', e.target.value)}
                  />
                  <select
                    value={form.rate_unit}
                    onChange={(e) => set('rate_unit', e.target.value)}
                  >
                    <option value="m3/s">m³/s</option>
                    <option value="m3/h">m³/h</option>
                    <option value="m3/d">m³/d</option>
                    <option value="L/s">L/s</option>
                    <option value="gpm_us">gpm(美制)</option>
                  </select>
                </div>
              </label>
              <label>
                时间单位
                <select
                  value={form.time_unit}
                  onChange={(e) => set('time_unit', e.target.value)}
                >
                  <option value="s">s</option>
                  <option value="min">min</option>
                  <option value="h">h</option>
                  <option value="d">d</option>
                </select>
              </label>
              <label>
                降深（水位）单位
                <select
                  value={form.head_unit}
                  onChange={(e) => set('head_unit', e.target.value)}
                >
                  <option value="m">m</option>
                  <option value="ft">ft</option>
                </select>
              </label>
            </div>
          </section>

          <section className="card">
            <h3>② 基准水位</h3>
            <div className="grid2">
              <label>
                抽水前静水位
                <input
                  type="number"
                  value={form.static_water_level}
                  onChange={(e) => set('static_water_level', e.target.value)}
                  placeholder="降深须以同一静水位为基准"
                />
              </label>
              <label>
                水位基准约定
                <select
                  value={form.level_datum}
                  onChange={(e) => set('level_datum', e.target.value)}
                >
                  <option value="above_msl">海拔（高于平均海平面）</option>
                  <option value="below_ground">地面以下埋深（正数）</option>
                </select>
              </label>
            </div>
            <label>
              基准备注（可选）
              <input
                type="text"
                value={form.datum_note}
                onChange={(e) => set('datum_note', e.target.value)}
                placeholder="如：统一换算至 1985 国家高程"
              />
            </label>
          </section>

          <section className="card">
            <h3>③ 参数边界（SI）</h3>
            <div className="grid2">
              <label>
                T 下限 (m²/s)
                <input
                  type="number"
                  step="any"
                  value={form.bounds.t_min_m2_s}
                  onChange={(e) => setBound('t_min_m2_s', e.target.value)}
                />
              </label>
              <label>
                T 上限 (m²/s)
                <input
                  type="number"
                  step="any"
                  value={form.bounds.t_max_m2_s}
                  onChange={(e) => setBound('t_max_m2_s', e.target.value)}
                />
              </label>
              <label>
                S 下限
                <input
                  type="number"
                  step="any"
                  value={form.bounds.s_min}
                  onChange={(e) => setBound('s_min', e.target.value)}
                />
              </label>
              <label>
                S 上限
                <input
                  type="number"
                  step="any"
                  value={form.bounds.s_max}
                  onChange={(e) => setBound('s_max', e.target.value)}
                />
              </label>
            </div>
          </section>

          <section className="card">
            <h3>④ 时间—降深数据</h3>
            <p className="muted small">
              每行“时间 降深”，支持逗号/制表符/空格分隔；缺测请留空或填{' '}
              <code>NA</code>，系统保持缺失并在图中显示缺口，不做插补。
            </p>
            <textarea
              rows={7}
              value={rawText}
              onChange={(e) => ingestText(e.target.value)}
              placeholder={'1\t0.12\n2\t0.20\n5\tNA\n8\t0.41'}
            />
            <div className="row-between">
              <label className="file-btn">
                导入 CSV/TXT
                <input type="file" accept=".csv,.txt,.tsv" hidden onChange={onFile} />
              </label>
              <span className="muted small">
                {form.observations.length} 行 · 有效 {validCount} · 缺测 {missCount}
              </span>
            </div>
          </section>

          <section className="card">
            <h3>核对数据集（合成）</h3>
            <div className="demo-row">
              <button onClick={() => loadDemo('clean')} disabled={busy}>
                1 已知参数
              </button>
              <button onClick={() => loadDemo('noisy')} disabled={busy}>
                2 噪声+缺测
              </button>
              <button onClick={() => loadDemo('unit_error')} disabled={busy}>
                3 距离单位错误
              </button>
            </div>
            {activeDemo === 'unit_error' && (
              <p className="warn-inline">
                该数据真实井距 300 ft，被错误录入为 1500 m——点击拟合后应出现贮水系数
                异常与单位核对提示。
              </p>
            )}
            <div className="row-between run-bar">
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={form.save}
                  onChange={(e) => set('save', e.target.checked)}
                />
                保存本次输入（可重现）
              </label>
              <button className="primary" onClick={runFit} disabled={busy}>
                {busy ? '计算中…' : '拟合 Theis 模型'}
              </button>
            </div>
            {error && <p className="error-text">{error}</p>}
          </section>

          {runs.length > 0 && (
            <section className="card">
              <h3>已保存运行（PostgreSQL）</h3>
              <ul className="runs-list">
                {runs.map((r) => (
                  <li key={r.id}>
                    <button
                      className="link-btn"
                      title="读取保存的结果"
                      onClick={() => loadRun(r.id, false)}
                    >
                      #{r.id} {r.project_name}
                    </button>
                    <span className="muted small">
                      {' '}
                      T={r.transmissivity_m2_s?.toExponential(2) ?? '—'} ·{' '}
                      S={r.storativity?.toExponential(2) ?? '—'}
                    </span>
                    <button
                      className="link-btn small"
                      title="用保存的原始输入重新拟合以验证重现"
                      onClick={() => loadRun(r.id, true)}
                    >
                      重新拟合
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>

        <div className="right">
          {result ? (
            <ResultsView result={result} />
          ) : (
            <section className="card placeholder">
              <p>导入或选择核对数据后点击“拟合”。</p>
              <p className="muted small">
                结果区将展示半对数降深曲线（含 Theis 拟合与缺测缺口）、残差图、
                参数与边界、输入检查和模型假设局限。
              </p>
            </section>
          )}
        </div>
      </div>

      <footer>
        Theis 解：s = Q/(4πT)·W(u)，u = r²S/(4Tt)。本工具不构成任何开采许可或水文
        行政结论。
      </footer>
    </div>
  )
}
