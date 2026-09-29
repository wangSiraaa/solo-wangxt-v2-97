import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'

/** Plotly wrapper. `traces`/`layout` are plain Plotly objects. */
export default function Plot({ traces, layout, config, height = 380 }) {
  const ref = useRef(null)

  useEffect(() => {
    if (!ref.current) return
    const fullLayout = {
      autosize: true,
      margin: { l: 60, r: 20, t: 36, b: 52 },
      paper_bgcolor: 'white',
      plot_bgcolor: '#fbfcfe',
      font: { family: 'system-ui, sans-serif', size: 12 },
      ...layout,
    }
    Plotly.react(ref.current, traces, fullLayout, {
      responsive: true,
      displaylogo: false,
      ...config,
    })
  }, [traces, layout, config])

  useEffect(() => {
    const el = ref.current
    return () => {
      if (el) Plotly.purge(el)
    }
  }, [])

  return <div ref={ref} style={{ width: '100%', height }} />
}
