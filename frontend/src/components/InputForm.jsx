import { useEffect, useState } from 'react';

// Parse pasted two-column text: "time,drawdown" per line.
// Empty cells / blank lines stay null (missing measurement) and are
// NEVER filled in. Accepts comma, semicolon, tab or whitespace separators
// and an optional header row.
export function parsePairs(text) {
  const lines = text.split(/\r?\n/);
  const times = [];
  const draws = [];
  let skippedHeader = false;
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    const cells = line.split(/[,;\t]|\s+/).map((c) => c.trim());
    if (cells.length < 2) continue;
    if (!skippedHeader && Number.isNaN(Number(cells[0]))) {
      skippedHeader = true; // e.g. "time_min,drawdown_m"
      continue;
    }
    const t = cells[0] === '' ? null : Number(cells[0]);
    const s = cells[1] === '' ? null : Number(cells[1]);
    if (t !== null && Number.isNaN(t)) continue;
    if (s !== null && Number.isNaN(s)) continue;
    times.push(t);
    draws.push(s);
  }
  return { times, draws };
}

const DEFAULTS = {
  name: '复核试验',
  distance: '100',
  distance_unit: 'm',
  pumping_rate: '120',
  pumping_rate_unit: 'm3/h',
  time_unit: 'min',
  t_min: '1e-9',
  t_max: '1e3',
  s_min: '1e-10',
  s_max: '1e0',
  weights: 'log',
};

export default function InputForm({ onFit, onSave, onLoadDemo, onLoadSaved, busy, savedIds }) {
  const [f, setF] = useState(DEFAULTS);
  const [dataText, setDataText] = useState('');
  const [parseNote, setParseNote] = useState('');

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  // Repopulate the whole form from a stored analysis snapshot.
  useEffect(() => {
    const handler = (ev) => {
      const p = ev.detail.payload;
      setF((cur) => ({
        ...cur,
        name: p.name ?? cur.name,
        distance: String(p.distance),
        distance_unit: p.distance_unit,
        pumping_rate: String(p.pumping_rate),
        pumping_rate_unit: p.pumping_rate_unit,
        time_unit: p.time_unit,
        t_min: String(p.t_min),
        t_max: String(p.t_max),
        s_min: String(p.s_min),
        s_max: String(p.s_max),
        weights: p.weights,
      }));
      updateParseNote(ev.detail.text);
    };
    window.addEventListener('theis:load-payload', handler);
    return () => window.removeEventListener('theis:load-payload', handler);
  }, []);

  const buildPayload = () => {
    const { times, draws } = parsePairs(dataText);
    return {
      name: f.name,
      distance: Number(f.distance),
      distance_unit: f.distance_unit,
      pumping_rate: Number(f.pumping_rate),
      pumping_rate_unit: f.pumping_rate_unit,
      time_unit: f.time_unit,
      times,
      drawdowns: draws,
      t_min: Number(f.t_min),
      t_max: Number(f.t_max),
      s_min: Number(f.s_min),
      s_max: Number(f.s_max),
      weights: f.weights,
    };
  };

  const updateParseNote = (text) => {
    setDataText(text);
    const { times, draws } = parsePairs(text);
    if (!times.length) { setParseNote(''); return; }
    const missing = draws.filter((d) => d === null).length;
    setParseNote(
      `已解析 ${times.length} 行；缺测 ${missing} 个（保持缺失，不插补）`
    );
  };

  const fillDemo = async (kind) => {
    const { defaults, text } = await onLoadDemo(kind);
    setF({ ...f, ...defaults });
    setDataText(text);
    updateParseNote(text);
  };

  return (
    <div className="panel">
      <h2>试验输入</h2>

      <label>试验名称</label>
      <input value={f.name} onChange={set('name')} />

      <div className="row">
        <div>
          <label>抽水井—观测井井距 r</label>
          <input type="number" step="any" value={f.distance} onChange={set('distance')} />
        </div>
        <div>
          <label>单位</label>
          <select value={f.distance_unit} onChange={set('distance_unit')}>
            <option value="m">m（米）</option>
            <option value="ft">ft（英尺）</option>
            <option value="cm">cm（厘米）</option>
          </select>
        </div>
      </div>
      <p className="hint">
        井距必须现场独立核对：单观测井无法识别米/英尺标错（S 与 r² 成反比耦合）。
      </p>

      <div className="row">
        <div>
          <label>恒定抽水流量 Q</label>
          <input type="number" step="any" value={f.pumping_rate} onChange={set('pumping_rate')} />
        </div>
        <div>
          <label>单位</label>
          <select value={f.pumping_rate_unit} onChange={set('pumping_rate_unit')}>
            <option value="m3/h">m³/h</option>
            <option value="m3/min">m³/min</option>
            <option value="m3/s">m³/s</option>
            <option value="L/s">L/s</option>
            <option value="gpm">gpm（美制加仑/分）</option>
          </select>
        </div>
      </div>

      <label>观测时间 / 降深（两列：时间, 降深 m；缺测行留空）</label>
      <textarea
        rows={7}
        placeholder={'time_min,drawdown_m\n1,0.12\n2,0.18\n5,\n10,0.34'}
        value={dataText}
        onChange={(e) => updateParseNote(e.target.value)}
      />
      <p className="hint">{parseNote || '降深以抽水前稳定水位为基准，恢复阶段数据不适用。'}</p>

      <div className="row">
        <div>
          <label>时间列单位</label>
          <select value={f.time_unit} onChange={set('time_unit')}>
            <option value="s">s</option>
            <option value="min">min</option>
            <option value="h">h</option>
            <option value="d">d</option>
          </select>
        </div>
        <div>
          <label>拟合权重</label>
          <select value={f.weights} onChange={set('weights')}>
            <option value="log">对数空间（早/晚期等权，推荐）</option>
            <option value="linear">线性（m）</option>
          </select>
        </div>
      </div>

      <h2 style={{ marginTop: 14 }}>参数搜索边界</h2>
      <div className="row">
        <div>
          <label>T 下界 (m²/s)</label>
          <input value={f.t_min} onChange={set('t_min')} />
        </div>
        <div>
          <label>T 上界 (m²/s)</label>
          <input value={f.t_max} onChange={set('t_max')} />
        </div>
      </div>
      <div className="row">
        <div>
          <label>S 下界</label>
          <input value={f.s_min} onChange={set('s_min')} />
        </div>
        <div>
          <label>S 上界</label>
          <input value={f.s_max} onChange={set('s_max')} />
        </div>
      </div>

      <div className="btns">
        <button disabled={busy} onClick={() => onFit(buildPayload())}>拟合复核</button>
        <button className="secondary" disabled={busy} onClick={() => onSave(buildPayload())}>
          拟合并保存
        </button>
      </div>

      <div className="btns">
        <button className="secondary" onClick={() => fillDemo('exact')}>
          填充：合成已知参数
        </button>
        <button className="secondary" onClick={() => fillDemo('noisy')}>
          填充：含噪声+缺测
        </button>
        <button className="secondary" onClick={() => fillDemo('wrong_unit')}>
          填充：井距单位错误
        </button>
      </div>

      {savedIds.length > 0 && (
        <>
          <label style={{ marginTop: 12 }}>已保存记录（点击可重新载入并重现）</label>
          <select onChange={(e) => e.target.value && onLoadSaved(Number(e.target.value))}
            defaultValue="">
            <option value="" disabled>选择记录…</option>
            {savedIds.map((r) => (
              <option key={r.id} value={r.id}>
                #{r.id} {r.name}（T={r.transmissivity_m2_s?.toExponential(2)}）
              </option>
            ))}
          </select>
        </>
      )}
    </div>
  );
}
