import { useEffect, useMemo, useState } from 'react'
import { getPlotPoints, type PlotSeries } from '../../api'
import { Markdown } from '../Markdown'
import type { PlotBlock, PlotParameter } from '../types'
import { PlotChart } from './PlotChart'
import { sampleTree } from './plotTree'

// The server samples the points at the parameter defaults. When a slider moves, the
// renderer re-samples from the server's expression tree; it never parses SymPy.
export function PlotBlockView({ block, lessonId }: { block: PlotBlock; lessonId: string }) {
  const [series, setSeries] = useState<PlotSeries[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [values, setValues] = useState<Record<string, number>>(() =>
    Object.fromEntries(block.parameters.map((p) => [p.name, p.default]))
  )
  const [moved, setMoved] = useState(false)

  useEffect(() => {
    let cancelled = false
    getPlotPoints(lessonId, block.id)
      .then((result) => !cancelled && setSeries(result))
      .catch((err: Error) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [lessonId, block.id])

  const shown = useMemo(
    () =>
      series && moved
        ? series.map((s) => ({ ...s, points: sampleTree(s.tree, block.x_domain, values) }))
        : series,
    [series, moved, values, block.x_domain]
  )

  const setValue = (name: string, value: number) => {
    setValues((current) => ({ ...current, [name]: value }))
    setMoved(true)
  }

  return (
    <figure className="card">
      {shown ? (
        <PlotChart series={shown} xDomain={block.x_domain} yDomain={block.y_domain} />
      ) : (
        <div className="plot-placeholder">{error ? `Could not load the plot: ${error}` : 'Loading plot'}</div>
      )}
      {block.parameters.length > 0 && (
        <div className="plot-parameters">
          {block.parameters.map((parameter) => (
            <ParameterSlider key={parameter.name} parameter={parameter} value={values[parameter.name]} onChange={setValue} />
          ))}
        </div>
      )}
      <figcaption>
        <Markdown inline>{block.caption}</Markdown>
      </figcaption>
    </figure>
  )
}

interface SliderProps {
  parameter: PlotParameter
  value: number
  onChange: (name: string, value: number) => void
}

function ParameterSlider({ parameter, value, onChange }: SliderProps) {
  const step = (parameter.max - parameter.min) / 100
  return (
    <label className="plot-parameter">
      <span>
        {parameter.name} = {Number(value.toPrecision(4))}
      </span>
      <input
        type="range"
        min={parameter.min}
        max={parameter.max}
        step={step}
        value={value}
        onChange={(event) => onChange(parameter.name, Number(event.target.value))}
      />
    </label>
  )
}
