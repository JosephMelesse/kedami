// The study and rest timer, as pure functions of the state and the current time.
// Remaining time comes from the phase's end timestamp, so it stays right in the background.

export type Phase = 'study' | 'rest'

export interface Durations {
  /** Whole minutes. */
  study: number
  rest: number
}

export type TimerState =
  | { status: 'idle' }
  | { status: 'running'; phase: Phase; endsAt: number }
  | { status: 'paused'; phase: Phase; remaining: number }

export const DEFAULT_DURATIONS: Durations = { study: 25, rest: 5 }
export const MIN_MINUTES = 1
export const MAX_MINUTES = 180
export const IDLE: TimerState = { status: 'idle' }

const MINUTE = 60_000

function length(phase: Phase, durations: Durations): number {
  return durations[phase] * MINUTE
}

function other(phase: Phase): Phase {
  return phase === 'study' ? 'rest' : 'study'
}

export function phaseOf(state: TimerState): Phase {
  return state.status === 'idle' ? 'study' : state.phase
}

export function start(state: TimerState, now: number, durations: Durations): TimerState {
  switch (state.status) {
    case 'idle':
      return { status: 'running', phase: 'study', endsAt: now + length('study', durations) }
    case 'paused':
      return { status: 'running', phase: state.phase, endsAt: now + state.remaining }
    case 'running':
      return state
  }
}

export function pause(state: TimerState, now: number): TimerState {
  if (state.status !== 'running') return state
  return { status: 'paused', phase: state.phase, remaining: Math.max(0, state.endsAt - now) }
}

/**
 * Move past any phases that have ended. If the window slept through several, the timer
 * lands in the right phase, and the alarm still plays only once.
 */
export function tick(state: TimerState, now: number, durations: Durations): { state: TimerState; alarm: boolean } {
  if (state.status !== 'running' || now < state.endsAt) return { state, alarm: false }
  let { phase, endsAt } = state
  while (now >= endsAt) {
    phase = other(phase)
    endsAt += length(phase, durations)
  }
  return { state: { status: 'running', phase, endsAt }, alarm: true }
}

export function remaining(state: TimerState, now: number, durations: Durations): number {
  switch (state.status) {
    case 'idle':
      return length('study', durations)
    case 'paused':
      return state.remaining
    case 'running':
      return Math.max(0, state.endsAt - now)
  }
}

/** Minutes and seconds, rounding up so a phase shows its full length when it starts. */
export function formatRemaining(ms: number): string {
  const seconds = Math.ceil(ms / 1000)
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

/** A whole number of minutes in range, or null for input that isn't one. */
export function parseMinutes(text: string): number | null {
  if (!/^\d+$/.test(text.trim())) return null
  const minutes = Number(text.trim())
  return minutes >= MIN_MINUTES && minutes <= MAX_MINUTES ? minutes : null
}
