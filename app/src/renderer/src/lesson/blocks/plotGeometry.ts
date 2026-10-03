// Pure geometry for plot blocks: ranges, ticks, and SVG paths.

export type Range = [number, number]
export type Point = [number, number | null]

export interface Frame {
  x: Range
  y: Range
  width: number
  height: number
}

/** The y range to draw: the block's own, or the data's extent padded by 5%. */
export function yRange(series: Point[][], yDomain: Range | null): Range {
  if (yDomain) return yDomain
  const ys = series.flat().flatMap(([, y]) => (y === null ? [] : [y]))
  if (ys.length === 0) return [-1, 1]
  const min = Math.min(...ys)
  const max = Math.max(...ys)
  if (min === max) return [min - 1, max + 1]
  const pad = (max - min) * 0.05
  return [min - pad, max + pad]
}

/** Round tick values covering [min, max], about `target` of them. */
export function niceTicks([min, max]: Range, target = 5): number[] {
  const raw = (max - min) / target
  const magnitude = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 5, 10].map((m) => m * magnitude).find((s) => s >= raw) ?? 10 * magnitude
  const ticks: number[] = []
  for (let i = Math.ceil(min / step); i * step <= max + step * 1e-9; i++) {
    ticks.push(Number((i * step).toPrecision(12)))
  }
  return ticks
}

export function scaleX(x: number, frame: Frame): number {
  return ((x - frame.x[0]) / (frame.x[1] - frame.x[0])) * frame.width
}

export function scaleY(y: number, frame: Frame): number {
  return frame.height - ((y - frame.y[0]) / (frame.y[1] - frame.y[0])) * frame.height
}

/**
 * An SVG path through the points. The line breaks where a value is missing, and
 * across jumps taller than the whole y range, so poles don't draw vertical lines.
 */
export function linePath(points: Point[], frame: Frame): string {
  const span = frame.y[1] - frame.y[0]
  let path = ''
  let previous: number | null = null
  for (const [x, y] of points) {
    if (y === null) {
      previous = null
      continue
    }
    const command = previous === null || Math.abs(y - previous) > span ? 'M' : 'L'
    path += `${command}${scaleX(x, frame).toFixed(2)},${scaleY(y, frame).toFixed(2)}`
    previous = y
  }
  return path
}
