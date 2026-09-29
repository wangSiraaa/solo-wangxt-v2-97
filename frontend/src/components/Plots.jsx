import Plotly from 'plotly.js-basic-dist-min';
import createPlotlyComponent from 'react-plotly.js/factory';

// basic-dist keeps the bundle small and includes scatter + line traces,
// which is everything the Theis review UI needs.
const Plot = createPlotlyComponent(Plotly);

const LAYOUT_BASE = {
  autosize: true,
  margin: { l: 60, r: 20, t: 30, b: 50 },
  legend: { orientation: 'h', y: -0.18 },
  font: { family: 'inherit', size: 12 },
  hovermode: 'closest',
};

export function DrawdownPlot({ result }) {
  const used = result.points.filter((p) => p.used_in_fit);
  const missing = result.points.filter((p) => !p.used_in_fit);

  const traces = [
    {
      x: result.curve_time_s,
      y: result.curve_drawdown_m,
      mode: 'lines',
      name: `Theis 拟合 (T=${formatSci(result.transmissivity_m2_s)}, S=${formatSci(result.storativity)})`,
      line: { color: '#1c64f2', width: 2 },
      hovertemplate: 't=%{x:.1f} s<br>s=%{y:.3f} m<extra></extra>',
    },
    {
      x: used.map((p) => p.time_s),
      y: used.map((p) => p.drawdown_m),
      mode: 'markers',
      name: '观测降深',
      marker: { color: '#111827', size: 6 },
      hovertemplate: 't=%{x:.1f} s<br>s=%{y:.3f} m<extra>观测</extra>',
    },
  ];
  if (missing.length) {
    // Missing measurements are shown explicitly ON the x-axis baseline;
    // they are never imputed and never carry a modelled value.
    traces.push({
      x: missing.map((p) => p.time_s),
      y: missing.map(() => 0),
      mode: 'markers',
      name: `缺测（${missing.length}，未插补）`,
      marker: { color: '#d64545', size: 9, symbol: 'triangle-down' },
      hovertemplate: 't=%{x:.1f} s<br>缺测<extra></extra>',
    });
  }

  return (
    <Plot
      className="plotbox"
      style={{ width: '100%', height: 360 }}
      data={traces}
      layout={{
        ...LAYOUT_BASE,
        title: { text: '降深-时间曲线（s–t）', font: { size: 14 } },
        xaxis: { title: '时间 t (s，对数轴)', type: 'log' },
        yaxis: { title: '降深 s (m)' },
      }}
      config={{ responsive: true, displaylogo: false }}
      useResizeHandler
    />
  );
}

export function ResidualPlot({ result }) {
  const used = result.points.filter((p) => p.used_in_fit);
  return (
    <Plot
      className="plotbox"
      style={{ width: '100%', height: 280 }}
      data={[
        {
          x: used.map((p) => p.time_s),
          y: used.map((p) => p.residual_m),
          mode: 'markers',
          name: '残差 (观测−拟合)',
          marker: { color: '#c05621', size: 6 },
          hovertemplate: 't=%{x:.1f} s<br>残差=%{y:.4f} m<extra></extra>',
        },
        {
          x: [
            result.curve_time_s[0],
            result.curve_time_s[result.curve_time_s.length - 1],
          ],
          y: [0, 0],
          mode: 'lines',
          name: '零残差线',
          line: { color: '#9aa5b1', dash: 'dash' },
          hoverinfo: 'skip',
        },
      ]}
      layout={{
        ...LAYOUT_BASE,
        title: { text: '残差图（用于发现系统性偏离）', font: { size: 14 } },
        xaxis: { title: '时间 t (s，对数轴)', type: 'log' },
        yaxis: { title: '残差 (m)' },
        showlegend: false,
        shapes: [
          {
            type: 'rect',
            xref: 'paper',
            x0: 0, x1: 1,
            y0: -result.rmse_m, y1: result.rmse_m,
            fillcolor: 'rgba(28,100,242,0.07)',
            line: { width: 0 },
            layer: 'below',
          },
        ],
      }}
      config={{ responsive: true, displaylogo: false }}
      useResizeHandler
    />
  );
}

function formatSci(x) {
  return Number(x).toExponential(2);
}
