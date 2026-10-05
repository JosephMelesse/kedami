import { describe, expect, it } from 'vitest'
import { readingBlock } from './readingPosition'

/** Stand-ins for block elements, measured only by their bottom edge. */
function blocks(...bottoms: number[]) {
  return bottoms.map((bottom, index) => ({ index, getBoundingClientRect: () => ({ bottom }) as DOMRect }))
}

describe('readingBlock', () => {
  it('is the first block whose bottom is below the header', () => {
    expect(readingBlock(blocks(-400, -10, 120, 700, 1400), 56)).toMatchObject({ index: 2 })
  })

  it('counts a block until its bottom edge passes the header', () => {
    expect(readingBlock(blocks(-100, 57, 600), 56)).toMatchObject({ index: 1 })
    expect(readingBlock(blocks(-100, 56, 600), 56)).toMatchObject({ index: 2 })
  })

  it('is the first block when the page is at the top', () => {
    expect(readingBlock(blocks(400, 900), 56)).toMatchObject({ index: 0 })
  })

  it('is the last block when every block is above the header', () => {
    expect(readingBlock(blocks(-900, -400, 20), 56)).toMatchObject({ index: 2 })
  })

  it('is nothing in a lesson with no blocks', () => {
    expect(readingBlock([], 56)).toBeNull()
  })

  it('measures only a few blocks in a long lesson', () => {
    let measured = 0
    const many = Array.from({ length: 1000 }, (_, index) => ({
      index,
      getBoundingClientRect: () => {
        measured += 1
        return { bottom: index * 100 - 50_000 } as DOMRect
      }
    }))
    expect(readingBlock(many, 56)).toMatchObject({ index: 501 })
    expect(measured).toBeLessThanOrEqual(11)
  })
})
