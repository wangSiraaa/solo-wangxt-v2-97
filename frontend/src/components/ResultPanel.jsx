import { DrawdownPlot, ResidualPlot } from './Plots.jsx';

const fSci = (x, d = 3) =>
  x === null || x === undefined || Number.isNaN(x)
    ? '—'
    : Number(x).toExponential(d);

function ciText(ci) {
  return `[${fSci(ci[0], 2)}, ${fSci(ci[1], 2)}]`;
}

export default function ResultPanel({ result, demoTruth }) {
  if (!result) {
    return (
      <div className="panel">
        <h2>复核结果</h2>
        <p className="small">
          导入或粘贴“时间, 降深”两列数据，选择单位与参数边界后点击“拟合复核”。
          首次使用可点左侧三个合成核对案例。
        </p>
      </div>
    );
  }

  const T_hit = result.hit_bounds.includes('T');
  const S_hit = result.hit_bounds.includes('S');

  return (
    <>
      {demoTruth && (
        <div className="alert warn">
          合成数据真实参数：T = {fSci(demoTruth.T_m2_s)} m²/s，S = {fSci(demoTruth.S)}。
          {demoTruth.note ? ` ${demoTruth.note}` : ''}
        </div>
      )}

      {result.warnings.length > 0 && (
        <div className="alert warn">
          <b>模型适用性提示</b>
          <ul>
            {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}
      {result.warnings.length === 0 && (
        <div className="alert" style={{ background: '#edf7f0', border: '1px solid #bce3c9' }}>
          <span className="tag-ok">未发现明显的模型适用性告警</span>
          <span className="small">（不代表模型必然成立，仍须核对井距、流量与现场条件）</span>
        </div>
      )}

      <div className="panel">
        <h2>拟合参数（SciPy 非线性最小二乘，Theis 模型）</h2>
        <div className="fit-meta">
          <span>实际采用井距：<b>{result.distance_m.toFixed(3)}</b> m</span>
          <span>实际采用流量：<b>{fSci(result.pumping_rate_m3_s, 4)}</b> m³/s</span>
          {result.saved_id && <span>已保存编号：<b>#{result.saved_id}</b></span>}
        </div>
        <table className="params">
          <thead>
            <tr><th>参数</th><th>拟合值</th><th>标准误</th><th>95% 置信区间</th><th>搜索边界</th></tr>
          </thead>
          <tbody>
            <tr>
              <td>导水系数 T (m²/s)</td>
              <td className="num">{fSci(result.transmissivity_m2_s)}</td>
              <td className="num">{fSci(result.t_se)}</td>
              <td className="num">{ciText(result.t_ci95)}</td>
              <td>
                <span className={`bound-pill${T_hit ? ' hit' : ''}`}>
                  {fSci(result.t_bounds[0], 1)} ~ {fSci(result.t_bounds[1], 1)}
                  {T_hit ? ' · 贴边!' : ''}
                </span>
              </td>
            </tr>
            <tr>
              <td>贮水系数 S (无量纲)</td>
              <td className="num">{fSci(result.storativity)}</td>
              <td className="num">{fSci(result.s_se)}</td>
              <td className="num">{ciText(result.s_ci95)}</td>
              <td>
                <span className={`bound-pill${S_hit ? ' hit' : ''}`}>
                  {fSci(result.s_bounds[0], 1)} ~ {fSci(result.s_bounds[1], 1)}
                  {S_hit ? ' · 贴边!' : ''}
                </span>
              </td>
            </tr>
          </tbody>
        </table>

        <h2 style={{ marginTop: 16 }}>拟合优度</h2>
        <div className="fit-meta">
          <span>R²：<b>{result.r_squared.toFixed(5)}</b></span>
          <span>RMSE：<b>{result.rmse_m.toFixed(4)}</b> m</span>
          <span>MAE：<b>{result.mae_m.toFixed(4)}</b> m</span>
          <span>最大|残差|：<b>{result.max_abs_residual_m.toFixed(4)}</b> m</span>
        </div>

        <DrawdownPlot result={result} />
        <ResidualPlot result={result} />
      </div>

      <div className="alert limit">
        <b>模型假设与局限（首版：均质承压含水层 / 恒定流量 / 单一观测井）</b>
        <ul>
          {result.limitations.map((l, i) => <li key={i}>{l}</li>)}
        </ul>
      </div>
    </>
  );
}
