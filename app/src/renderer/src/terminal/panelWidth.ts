// The Terminal panel's width, kept to what leaves the screen beside it usable, and remembered in this
// window's local storage. See architecture/agent-mode.md, Terminal panel.
const KEY = 'kedami.terminalWidth'
export const MIN_WIDTH = 320
// The narrowest the screen beside the panel gets.
export const MIN_CONTENT = 360
const FIRST_SHARE = 0.4

/** The width kept between MIN_WIDTH and the window's width less MIN_CONTENT, preferring MIN_WIDTH when both can't hold. */
export function clampWidth(width: number, windowWidth: number): number {
  return Math.round(Math.max(MIN_WIDTH, Math.min(width, windowWidth - MIN_CONTENT)))
}

export function loadWidth(windowWidth: number, storage: Storage = localStorage): number {
  let saved = NaN
  try {
    saved = Number(storage.getItem(KEY))
  } catch {
    // Storage may be unavailable; fall back to the first width.
  }
  return clampWidth(Number.isFinite(saved) && saved > 0 ? saved : windowWidth * FIRST_SHARE, windowWidth)
}

export function saveWidth(width: number, storage: Storage = localStorage): void {
  try {
    storage.setItem(KEY, String(Math.round(width)))
  } catch {
    // Not remembered, which only costs the width next launch.
  }
}
