import { useEffect, useRef, useState } from 'react'
import alarmUrl from '../assets/alarm.wav'
import { loadDurations, saveDurations } from './durations'
import {
  type Durations,
  formatRemaining,
  IDLE,
  parseMinutes,
  pause,
  phaseOf,
  remaining,
  start,
  type TimerState,
  tick
} from './timer'

const TICK_MS = 250
const PHASE_LABELS = { study: 'Study', rest: 'Rest' }

export function PomodoroTimer() {
  const [durations, setDurations] = useState<Durations>(loadDurations)
  const [state, setState] = useState<TimerState>(IDLE)
  const [now, setNow] = useState(() => Date.now())
  const alarm = useRef<HTMLAudioElement | null>(null)
  const current = useRef(state)
  current.current = state

  useEffect(() => {
    if (state.status !== 'running') return
    const timer = setInterval(() => {
      const at = Date.now()
      const next = tick(current.current, at, durations)
      if (next.alarm) {
        alarm.current ??= new Audio(alarmUrl)
        alarm.current.currentTime = 0
        alarm.current.play().catch(() => {})
      }
      current.current = next.state
      setState(next.state)
      setNow(at)
    }, TICK_MS)
    return () => clearInterval(timer)
  }, [state.status, durations])

  const update = (change: Partial<Durations>) => {
    const next = { ...durations, ...change }
    setDurations(next)
    saveDurations(next)
  }

  const running = state.status === 'running'
  return (
    <div className="pomodoro">
      {state.status === 'idle' ? (
        <>
          <MinutesInput label="Study" value={durations.study} onChange={(study) => update({ study })} />
          <MinutesInput label="Rest" value={durations.rest} onChange={(rest) => update({ rest })} />
        </>
      ) : (
        <span className="pomodoro-phase">{PHASE_LABELS[phaseOf(state)]}</span>
      )}
      <span className="pomodoro-time" role="timer">
        {formatRemaining(remaining(state, now, durations))}
      </span>
      <button
        type="button"
        className="button"
        onClick={() => {
          const at = Date.now()
          setNow(at)
          setState(running ? pause(state, at) : start(state, at, durations))
        }}
      >
        {running ? 'Pause' : 'Start'}
      </button>
      <button type="button" className="button" disabled={state.status === 'idle'} onClick={() => setState(IDLE)}>
        Reset
      </button>
    </div>
  )
}

interface MinutesInputProps {
  label: string
  value: number
  onChange: (minutes: number) => void
}

/** A whole number of minutes. Text that isn't one reverts when the field loses focus. */
function MinutesInput({ label, value, onChange }: MinutesInputProps) {
  const [text, setText] = useState(String(value))
  useEffect(() => setText(String(value)), [value])
  return (
    <label className="pomodoro-field">
      <span className="muted">{label}</span>
      <input
        className="text-input pomodoro-minutes"
        inputMode="numeric"
        aria-label={`${label} minutes`}
        value={text}
        onChange={(event) => {
          setText(event.target.value)
          const minutes = parseMinutes(event.target.value)
          if (minutes !== null) onChange(minutes)
        }}
        onBlur={() => setText(String(value))}
      />
    </label>
  )
}
