import type { CSSProperties } from 'react'
import type { PlotSeries } from '../../api'
import { type Frame, type Range, linePath, niceTicks, scaleX, scaleY, yRange } from './plotGeometry'

const WIDTH = 640
const HEIGHT = 320
const MARGIN = { top: 16, right: 16, bottom: 32, left: 48 }

// Neutral line styles from the tokens; the accent is reserved for actions and progress.
// Set through style, since SVG presentation attributes don't resolve CSS variables.
const LINE_STYLES: CSSProperties[] = [
  { stroke: 'var(--text)' },
  { stroke: 'var(--text-muted)' },
  { stroke: 'var(--text)', strokeDasharray: '6 6' },
  { stroke: 'var(--text-muted)', strokeDasharray: '6 6' }
]

function lineStyle(index: number): CSSProperties {
  return LINE_STYLES[index % LINE_STYLES.length]
}

interface PlotChartProps {
  series: PlotSeries[]
  xDomain: Range
  yDomain: Range | null
}

export function PlotChart({ series, xDomain, yDomain }: PlotChartProps) {
  const frame: Frame = {
    x: xDomain,
    y: yRange(
      series.map((s) => s.points),
      yDomain
    ),
    width: WIDTH - MARGIN.left - MARGIN.right,
    height: HEIGHT - MARGIN.top - MARGIN.bottom
  }

  return (
    <>
      <svg className="plot-svg" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img">
        <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
          {niceTicks(frame.x).map((x) => (
            <g key={`x${x}`}>
              <line className="plot-grid" x1={scaleX(x, frame)} x2={scaleX(x, frame)} y1={0} y2={frame.height} />
              <text className="plot-tick" x={scaleX(x, frame)} y={frame.height + 20} textAnchor="middle">
                {x}
              </text>
            </g>
          ))}
          {niceTicks(frame.y).map((y) => (
            <g key={`y${y}`}>
              <line className="plot-grid" x1={0} x2={frame.width} y1={scaleY(y, frame)} y2={scaleY(y, frame)} />
              <text className="plot-tick" x={-8} y={scaleY(y, frame) + 4} textAnchor="end">
                {y}
              </text>
            </g>
          ))}
          {/* A nested svg clips the lines to the plot area. */}
          <svg width={frame.width} height={frame.height} overflow="hidden">
            {series.map((s, index) => (
              <path key={s.label} className="plot-line" d={linePath(s.points, frame)} style={lineStyle(index)} />
            ))}
          </svg>
        </g>
      </svg>
      <ul className="plot-legend">
        {series.map((s, index) => (
          <li key={s.label}>
            <svg width="24" height="8" aria-hidden="true">
              <line x1="0" x2="24" y1="4" y2="4" strokeWidth="2" style={lineStyle(index)} />
            </svg>
            {s.label}
          </li>
        ))}
      </ul>
    </>
  )
}
