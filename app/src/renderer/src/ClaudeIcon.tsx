// Claude Code's little pixel robot, as its startup banner draws it in block characters:
//
//    ▐▛███▜▌
//   ▝▜█████▛▘
//     ▘▘ ▝▝
//
// Each character is a 2 by 2 grid of quarter cells, and a terminal cell is twice as tall as it is wide, so each
// quarter is drawn 1 wide and 2 tall. Inline, so nothing is fetched, and single-color, so it takes its color from
// the design tokens.

// One string per row of quarter cells: # is drawn, . is empty. The gaps in the second row are its eyes.
const ROWS = [
  '...############...',
  '...##.######.##...',
  '.################.',
  '...############...',
  '....#.#....#.#....'
]
const WIDTH = ROWS[0].length

/** Each row's filled runs, as [x, y, width]. */
const RUNS = ROWS.flatMap((row, y) =>
  [...row.matchAll(/#+/g)].map((run): [number, number, number] => [run.index ?? 0, y, run[0].length])
)

export function ClaudeIcon({ width = 22 }: { width?: number }) {
  const height = (width * ROWS.length * 2) / WIDTH
  return (
    <svg
      className="claude-icon"
      viewBox={`0 0 ${WIDTH} ${ROWS.length * 2}`}
      width={width}
      height={height}
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      {RUNS.map(([x, y, length]) => (
        <rect key={`${x}-${y}`} x={x} y={y * 2} width={length} height={2} fill="currentColor" />
      ))}
    </svg>
  )
}
