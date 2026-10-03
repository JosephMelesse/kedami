import { useEffect, useState } from 'react'
import { getPlotPoints, type PlotSeries } from '../../api'
import type { PlotBlock } from '../types'
import { PlotChart } from './PlotChart'

// Points are sampled by the server, so the renderer never parses SymPy.
// Parameter sliders arrive in build step 2; until then parameters sit at their defaults.
export function PlotBlockView({ block, lessonId }: { block: PlotBlock; lessonId: string }) {
  const [series, setSeries] = useState<PlotSeries[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getPlotPoints(lessonId, block.id)
      .then((result) => !cancelled && setSeries(result))
      .catch((err: Error) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [lessonId, block.id])

  return (
    <figure className="card">
      {series ? (
        <PlotChart series={series} xDomain={block.x_domain} yDomain={block.y_domain} />
      ) : (
        <div className="plot-placeholder">{error ? `Could not load the plot: ${error}` : 'Loading plot'}</div>
      )}
      <figcaption>{block.caption}</figcaption>
    </figure>
  )
}
