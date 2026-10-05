// Where the student is reading: the topmost block still on screen below the sticky app header.

/** Seconds of no scrolling before the position is saved. */
export const SAVE_DELAY_MS = 1000

/**
 * The first block whose bottom edge is below the header, or the last block if all are above it.
 * Blocks are in page order, so their bottoms only grow, and a binary search measures only a few.
 */
export function readingBlock<T extends Pick<Element, 'getBoundingClientRect'>>(
  blocks: readonly T[],
  headerBottom: number
): T | null {
  if (blocks.length === 0) return null
  let low = 0
  let high = blocks.length - 1
  while (low < high) {
    const middle = Math.floor((low + high) / 2)
    if (blocks[middle].getBoundingClientRect().bottom > headerBottom) high = middle
    else low = middle + 1
  }
  return blocks[low]
}

export function blockElements(root: ParentNode): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>('[data-block-id]')]
}

export function headerBottom(): number {
  return document.querySelector('.app-header')?.getBoundingClientRect().bottom ?? 0
}
