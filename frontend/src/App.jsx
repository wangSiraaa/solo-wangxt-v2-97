import { useEffect, useState } from 'react';
import { api } from './api.js';
import InputForm from './components/InputForm.jsx';
import ResultPanel from './components/ResultPanel.jsx';

function pairsToText(payload) {
  return payload.times
    .map((t, i) => `${t ?? ''},${payload.drawdowns[i] ?? ''}`)
    .join('\n');
}

export default function App() {
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState([]);
  const [truth, setTruth] = useState(null);

  const refreshList = () => api.list().then(setSaved).catch(() => {});
  useEffect(() => { refreshList(); }, []);

  const run = async (payload, save = false) => {
    setBusy(true);
    setError('');
    try {
      const out = save ? await api.save(payload) : await api.fit(payload);
      setResult(out);
      if (save) refreshList();
    } catch (e) {
      setResult(null);
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  // Demo datasets come pre-shaped like a FitRequest; the form is filled
  // from them and the fit is run immediately for verification.
  const loadDemo = async (kind) => {
    setBusy(true);
    setError('');
    try {
      const p = await fetch(`/api/demo/${kind}`).then((r) => r.json());
      const { _truth, ...payload } = p;
      setTruth(_truth ?? null);
      // Run the fit immediately so reviewers see recovery at a glance.
      const out = await api.fit(payload);
      setResult(out);
      // Also return field defaults + text so the form reflects the data.
      return {
        defaults: {
          name: payload.name,
          distance: String(payload.distance),
          distance_unit: payload.distance_unit,
          pumping_rate: String(payload.pumping_rate),
          pumping_rate_unit: payload.pumping_rate_unit,
          time_unit: payload.time_unit,
          t_min: String(payload.t_min),
          t_max: String(payload.t_max),
          s_min: String(payload.s_min),
          s_max: String(payload.s_max),
          weights: payload.weights,
        },
        text: pairsToText(payload),
      };
    } catch (e) {
      setError(e.message);
      throw e;
    } finally {
      setBusy(false);
    }
  };

  // Load a previously saved row: repopulate + reproduce the fit via the
  // dedicated refit endpoint (server-side determinism check included).
  const loadSaved = async (id) => {
    setBusy(true);
    setError('');
    try {
      const detail = await api.get(id);
      const payload = detail.input_json;
      const out = await api.refit(id);
      setResult(out);
      setTruth(null);
      // Reflect stored input in the form fields as well.
      setFormFromPayload(payload);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  // Lightweight cross-component fill: dispatch a CustomEvent the form
  // listens for (keeps form state local without a state library).
  const setFormFromPayload = (payload) => {
    window.dispatchEvent(
      new CustomEvent('theis:load-payload', {
        detail: { payload, text: pairsToText(payload) },
      })
    );
  };

  return (
    <div className="app">
      <header>
        <h1>抽水试验降深复核 · Theis 模型拟合</h1>
        <div className="sub">
          均质承压含水层 · 恒定流量 · 单一观测井 ｜ FastAPI + SciPy + PostgreSQL ｜
          React + Plotly.js
        </div>
      </header>

      <div className="banner">
        本工具仅用于抽水试验参数（<b>T、S</b>）解释与降深曲线复核，
        <strong>不输出任何开采许可或取水许可结论</strong>。
        模型假设不满足时会在下方明确提示局限。
      </div>

      <div className="grid">
        <div>
          <InputForm
            busy={busy}
            onFit={(p) => { setTruth(null); run(p, false); }}
            onSave={(p) => { setTruth(null); run(p, true); }}
            onLoadDemo={loadDemo}
            onLoadSaved={loadSaved}
            savedIds={saved}
          />
          {error && <div className="alert error"><b>无法拟合：</b>{error}</div>}
        </div>
        <div>
          <ResultPanel result={result} demoTruth={truth} />
        </div>
      </div>
    </div>
  );
}
