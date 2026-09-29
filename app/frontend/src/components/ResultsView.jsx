import Plot from './Plot.jsx'
import Diagnostics from './Diagnostics.jsx'

const fmt = (x, n = 4) =>
  x === null || x === undefined || Number.isNaN(x)
    ? '—'
    : Number(x).toExponential(n)

export default function ResultsView({ result }) {
  if (!result) return null

  const obs = result.observations_si ?? []
  const valid = obs.filter((o) => !o.missing)
  const missing = obs.filter((o) => o.missing)
  const curve = result.curve ?? []

  // Convert seconds -> minutes for plotting (readings are entered in min here).
  const tUnit = result.meta?.time_unit ?? 'min'
  const factor = { s: 1, min: 1 / 60, h: 1 / 3600, d: 1 / 86400 }[tUnit]
  const headFactor = (result.meta?.head_unit ?? 'm') === 'ft' ? 1 / 0.3048 : 1

  const observedTrace = {
    x: valid.map((o) => o.t_s * factor),
    y: valid.map((o) => o.drawdown_m * headFactor),
    mode: 'markers',
    type: 'scatter',
    name: '实测降深',
    marker: { size: 8, color: '#1f5fae' },
    hovertemplate: 't=%{x:.3g} %{text}<br>s=%{y:.4g}<extra></extra>',
    text: valid.map(() => tUnit),
  }
  const modelTrace = {
    x: curve.map((c) => c.t_s * factor),
    y: curve.map((c) => (c.drawdown_model_m ?? NaN) * headFactor),
    mode: 'lines',
    type: 'scatter',
    name: 'Theis 拟合',
    line: { color: '#d9534f', width: 2.5 },
  }
  const missingTrace = {
    x: missing.map((o) => (o.t_s ?? NaN) * factor),
    y: missing.map((o) => (o.drawdown_model_m ?? NaN) * headFactor),
    mode: 'markers',
    type: 'scatter',
    name: `缺测点（模型位置 n=${missing.length}）`,
    marker: { size: 11, color: '#9aa5b1', symbol: 'x-open' },
  }

  const ddLayout = {
    title: '观测井降深曲线（半对数）',
    xaxis: {
      title: `时间 (${tUnit})`,
      type: 'log',
      exponentformat: 'power',
    },
    yaxis: {
      title: `降深 (${result.meta?.head_unit ?? 'm'})`,
      autorange: 'reversed',
    },
    legend: { orientation: 'h', y: -0.22 },
  }

  const residTrace = {
    x: valid.map((o) => o.t_s * factor),
    y: valid.map((o) => (o.residual_m ?? NaN) * headFactor),
    mode: 'markers+lines',
    type: 'scatter',
    name: '残差（实测 − 模型）',
    marker: { size: 7, color: '#5b3fa2' },
    line: { width: 1, color: '#9a86d6' },
  }
  const zeroTrace = {
    x: curve.length
      ? [
          curve[0].t_s * factor,
          curve[curve.length - 1].t_s * factor,
        ]
      : [0, 1],
    y: [0, 0],
    mode: 'lines',
    type: 'scatter',
    name: '零残差',
    line: { dash: 'dash', color: '#999' },
  }
  const residLayout = {
    title: '残差图（检出早期井储、晚期边界/越流特征）',
    xaxis: { title: `时间 (${tUnit})`, type: 'log' },
    yaxis: { title: `残差 (${result.meta?.head_unit ?? 'm'})` },
    showlegend: false,
    height: 260,
  }

  const T = result.transmissivity_m2_s
  const S = result.storativity
  const bounds = result.meta?.bounds

  return (
    <div className="results">
      <section className="card params">
        <h3>拟合参数</h3>
        {result.converged ? (
          <>
            <table>
              <tbody>
                <tr>
                  <th>导水系数 T</th>
                  <td>{fmt(T)} m²/s</td>
                  <td className="muted">= {T ? (T * 86400).toExponential(4) : '—'} m²/d</td>
                </tr>
                <tr>
                  <th>贮水系数 S</th>
                  <td>{fmt(S)}</td>
                  <td className="muted">无量纲（承压含水层常见 1e-6 ~ 1e-3）</td>
                </tr>
                <tr>
                  <th>RMSE</th>
                  <td>
                    {result.rmse_head
                      ? `${result.rmse_head.m.toExponential(3)} m`
                      : '—'}
                  </td>
                  <td className="muted">R² = {result.r_squared?.toFixed(5) ?? '—'}</td>
                </tr>
                <tr>
                  <th>有效测点</th>
                  <td>{result.n_points}</td>
                  <td className="muted">缺测 {result.n_missing} 个（保留为缺口）</td>
                </tr>
              </tbody>
            </table>
            {bounds && (
              <p className="muted small">
                参数边界：T ∈ [{fmt(bounds.t_min_m2_s, 2)},{' '}
                {fmt(bounds.t_max_m2_s, 2)}] m²/s；S ∈ [{bounds.s_min.toExponential(1)},{' '}
                {bounds.s_max.toExponential(1)}]
              </p>
            )}
          </>
        ) : (
          <p className="error-text">{result.message}</p>
        )}
        {result.run_id ? (
          <p className="saved-tag">已保存，运行编号 #{result.run_id}（可凭原始输入重现）</p>
        ) : null}
      </section>

      {result.converged && (
        <>
          <section className="card">
            <Plot traces={[modelTrace, observedTrace, missingTrace]} layout={ddLayout} />
          </section>
          <section className="card">
            <Plot traces={[zeroTrace, residTrace]} layout={residLayout} height={280} />
          </section>
        </>
      )}

      <Diagnostics title="输入检查（单位 / 基准水位 / 缺失）" items={result.input_checks} />
      <Diagnostics title="模型假设与拟合局限" items={result.diagnostics} />
    </div>
  )
}
