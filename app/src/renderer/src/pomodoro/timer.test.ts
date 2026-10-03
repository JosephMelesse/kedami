import { describe, expect, it } from 'vitest'
import { formatRemaining, IDLE, parseMinutes, pause, phaseOf, remaining, start, tick, type TimerState } from './timer'

const MIN = 60_000
const durations = { study: 25, rest: 5 }

describe('starting, pausing, and resetting', () => {
  it('starts a study phase from idle', () => {
    expect(start(IDLE, 1000, durations)).toEqual({ status: 'running', phase: 'study', endsAt: 1000 + 25 * MIN })
  })

  it('shows the full study length while idle', () => {
    expect(remaining(IDLE, 0, durations)).toBe(25 * MIN)
    expect(phaseOf(IDLE)).toBe('study')
  })

  it('pausing keeps the time left, and resuming continues from it', () => {
    const running = start(IDLE, 0, durations)
    const paused = pause(running, 10 * MIN)
    expect(paused).toEqual({ status: 'paused', phase: 'study', remaining: 15 * MIN })
    // Time spent paused doesn't count.
    expect(remaining(paused, 99 * MIN, durations)).toBe(15 * MIN)
    const resumed = start(paused, 50 * MIN, durations)
    expect(resumed).toEqual({ status: 'running', phase: 'study', endsAt: 65 * MIN })
  })

  it('ignores start while running and pause while not running', () => {
    const running = start(IDLE, 0, durations)
    expect(start(running, 5 * MIN, durations)).toBe(running)
    expect(pause(IDLE, 0)).toBe(IDLE)
    const paused = pause(running, MIN)
    expect(pause(paused, 2 * MIN)).toBe(paused)
  })

  it('a pause after the phase ended keeps no negative time', () => {
    expect(pause({ status: 'running', phase: 'rest', endsAt: 100 }, 500)).toEqual({ status: 'paused', phase: 'rest', remaining: 0 })
  })
})

describe('phases', () => {
  const running: TimerState = { status: 'running', phase: 'study', endsAt: 25 * MIN }

  it('does nothing before the phase ends', () => {
    expect(tick(running, 25 * MIN - 1, durations)).toEqual({ state: running, alarm: false })
    expect(remaining(running, 25 * MIN - 1, durations)).toBe(1)
  })

  it('switches to rest exactly at the end, with the alarm', () => {
    expect(tick(running, 25 * MIN, durations)).toEqual({
      state: { status: 'running', phase: 'rest', endsAt: 30 * MIN },
      alarm: true
    })
  })

  it('switches back to study after rest', () => {
    const rest: TimerState = { status: 'running', phase: 'rest', endsAt: 30 * MIN }
    expect(tick(rest, 30 * MIN + 5, durations).state).toEqual({ status: 'running', phase: 'study', endsAt: 55 * MIN })
  })

  it('keeps time from the scheduled end, not from when the tick arrived', () => {
    // A tick 40 s late still ends the rest phase at 30 minutes.
    const { state } = tick(running, 25 * MIN + 40_000, durations)
    expect(remaining(state, 25 * MIN + 40_000, durations)).toBe(5 * MIN - 40_000)
  })

  it('lands in the right phase after sleeping through several, with one alarm', () => {
    // Study ends at 25, rest at 30, study at 55, rest at 60: at 57 minutes it is rest again.
    expect(tick(running, 57 * MIN, durations)).toEqual({
      state: { status: 'running', phase: 'rest', endsAt: 60 * MIN },
      alarm: true
    })
  })

  it('leaves idle and paused timers alone', () => {
    const paused: TimerState = { status: 'paused', phase: 'rest', remaining: MIN }
    expect(tick(IDLE, 99 * MIN, durations)).toEqual({ state: IDLE, alarm: false })
    expect(tick(paused, 99 * MIN, durations)).toEqual({ state: paused, alarm: false })
  })
})

describe('formatRemaining', () => {
  it.each([
    [25 * MIN, '25:00'],
    [25 * MIN - 1, '25:00'],
    [61_000, '1:01'],
    [59_001, '1:00'],
    [999, '0:01'],
    [0, '0:00'],
    [180 * MIN, '180:00']
  ])('%i ms is %s', (ms, text) => {
    expect(formatRemaining(ms)).toBe(text)
  })
})

describe('parseMinutes', () => {
  it.each([
    ['25', 25],
    [' 5 ', 5],
    ['1', 1],
    ['180', 180]
  ])('accepts %s', (text, minutes) => {
    expect(parseMinutes(text)).toBe(minutes)
  })

  it.each(['0', '181', '2.5', '-3', '', 'ten', '1e2'])('rejects %s', (text) => {
    expect(parseMinutes(text)).toBeNull()
  })
})
