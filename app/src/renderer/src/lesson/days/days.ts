// Finish lines: a lesson split into days at block boundaries. See Finish lines in architecture/ui.md.

import { blockElements } from '../reading/readingPosition'

export const MAX_DAYS = 30
/** How long "Done for today" shows after a finish line is reached. */
export const NOTE_MS = 4000

/** Where a block's part of the lesson starts, in page coordinates. */
export interface Boundary {
  id: string
  top: number
}

/**
 * The blocks that start day 2 onward, at the block boundaries nearest to equal heights.
 * `boundaries` lists every block in order, the first starting day 1, and `end` is where the last block ends.
 * Each day keeps at least one block, so asking for more days than blocks gives one day per block.
 */
export function splitDays(boundaries: readonly Boundary[], end: number, days: number): string[] {
  const count = Math.min(days, boundaries.length)
  if (count <= 1) return []
  const start = boundaries[0].top
  const starts: string[] = []
  let previous = 0
  for (let day = 1; day < count; day++) {
    const target = start + ((end - start) * day) / count
    // Leave a block for each day still to come.
    const last = boundaries.length - (count - day)
    let best = previous + 1
    for (let index = best + 1; index <= last; index++) {
      if (Math.abs(boundaries[index].top - target) < Math.abs(boundaries[best].top - target)) best = index
    }
    starts.push(boundaries[best].id)
    previous = best
  }
  return starts
}

export interface DayProgress {
  /** Finish lines passed, counting the end of a split lesson as its last line. */
  reached: number
  /** How far through the current day, from 0 to 1. */
  fill: number
}

/**
 * Where the reading point is among the days. `lines` are the finish lines' page positions in order,
 * and `start` and `end` are where the lesson's blocks start and end.
 */
export function dayProgress(lines: readonly number[], start: number, end: number, point: number): DayProgress {
  const passed = lines.filter((line) => point >= line).length
  if (point >= end) return { reached: passed + (lines.length > 0 ? 1 : 0), fill: 1 }
  const bounds = [start, ...lines, end]
  const from = bounds[passed]
  const to = bounds[passed + 1]
  return { reached: passed, fill: to > from ? Math.min(1, Math.max(0, (point - from) / (to - from))) : 1 }
}

// Measuring the rendered lesson, in page coordinates.

function pageTop(element: Element): number {
  return element.getBoundingClientRect().top + window.scrollY
}

function pageBottom(element: Element): number {
  return element.getBoundingClientRect().bottom + window.scrollY
}

/** Each block's start. A block that opens its section starts at the section, so its heading goes with it. */
export function boundaries(root: ParentNode): Boundary[] {
  return blockElements(root).map((block) => {
    const section = block.closest('.lesson-section')
    const opens = section?.querySelector('[data-block-id]') === block
    return { id: block.dataset.blockId!, top: pageTop(opens && section ? section : block) }
  })
}

/** Where the last block ends, or null in a lesson with no blocks. */
export function lessonEnd(root: ParentNode): number | null {
  const last = blockElements(root).at(-1)
  return last ? pageBottom(last) : null
}

/** The day progress at the current scroll position. The reading point is the bottom edge of the window. */
export function measureDays(root: ParentNode): DayProgress | null {
  const first = blockElements(root)[0]
  const end = lessonEnd(root)
  if (!first || end === null) return null
  // A line is passed once all of it is in view.
  const lines = [...root.querySelectorAll('[data-finish-line]')].map(pageBottom)
  return dayProgress(lines, pageTop(first), end, window.scrollY + window.innerHeight)
}
