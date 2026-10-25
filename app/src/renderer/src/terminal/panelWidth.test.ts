import { describe, expect, it } from 'vitest'
import { clampWidth, loadWidth, MIN_WIDTH, saveWidth } from './panelWidth'

function memoryStorage(): Storage {
  const items = new Map<string, string>()
  return {
    getItem: (key) => items.get(key) ?? null,
    setItem: (key, value) => void items.set(key, value),
    removeItem: (key) => void items.delete(key),
    clear: () => items.clear(),
    key: () => null,
    get length() {
      return items.size
    }
  }
}

describe('the terminal panel width', () => {
  it('stays between the minimum and what leaves the content 360px', () => {
    expect(clampWidth(100, 1200)).toBe(MIN_WIDTH)
    expect(clampWidth(500, 1200)).toBe(500)
    expect(clampWidth(1000, 1200)).toBe(840)
    // Too narrow for both: the panel keeps its minimum.
    expect(clampWidth(500, 600)).toBe(MIN_WIDTH)
  })

  it('starts at 40% of the window, then is remembered', () => {
    const storage = memoryStorage()
    expect(loadWidth(1200, storage)).toBe(480)
    saveWidth(612.4, storage)
    expect(loadWidth(1200, storage)).toBe(612)
    // A remembered width still fits a smaller window.
    expect(loadWidth(800, storage)).toBe(440)
  })

  it('ignores a saved value that is not a width, and storage that throws', () => {
    const storage = memoryStorage()
    storage.setItem('kedami.terminalWidth', 'wide')
    expect(loadWidth(1000, storage)).toBe(400)
    const broken = { getItem: () => { throw new Error('denied') }, setItem: () => { throw new Error('denied') } } as unknown as Storage
    expect(loadWidth(1000, broken)).toBe(400)
    expect(() => saveWidth(500, broken)).not.toThrow()
  })
})
