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

interface PomodoroTimerProps {
  /** Called with the time left whenever it changes during rest, running or paused, and with null otherwise. */
  onRest?: (time: string | null) => void
}

export function PomodoroTimer({ onRest }: PomodoroTimerProps) {
  const [durations, setDurations] = useState<Durations>(loadDurations)
  const [state, setState] = useState<TimerState>(IDLE)
  const [now, setNow] = useState(() => Date.now())
  // In a narrow window the controls collapse behind a button showing the remaining time.
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const alarm = useRef<HTMLAudioElement | null>(null)
  const current = useRef(state)
  current.current = state

  useEffect(() => {
    if (!open) return
    const close = (event: Event) => {
      if (event instanceof KeyboardEvent ? event.key === 'Escape' : !root.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

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

  const stamp = () => {
    const at = Date.now()
    setNow(at)
    return at
  }
  const time = formatRemaining(remaining(state, now, durations))
  const phase = PHASE_LABELS[phaseOf(state)]
  const restTime = state.status !== 'idle' && state.phase === 'rest' ? time : null

  useEffect(() => onRest?.(restTime), [onRest, restTime])

  // Once started, only the phase and the remaining time show. Clicking them pauses or resumes;
  // a paused timer also offers Stop.
  if (state.status !== 'idle') {
    const running = state.status === 'running'
    return (
      <div className="pomodoro">
        <button
          type="button"
          className={running ? 'pomodoro-counter' : 'pomodoro-counter paused'}
          aria-label={`${running ? 'Pause' : 'Resume'} timer, ${phase} ${time}`}
          onClick={() => setState(running ? pause(state, stamp()) : start(state, stamp(), durations))}
        >
          <span className="pomodoro-phase">{phase}</span>
          <span className="pomodoro-time" role="timer">
            {time}
          </span>
        </button>
        {!running && (
          <button type="button" className="button" onClick={() => setState(IDLE)}>
            Stop
          </button>
        )}
      </div>
    )
  }

  // Reset. In a narrow window the inputs collapse behind a button showing the study time.
  return (
    <div className="pomodoro" ref={root}>
      <button
        type="button"
        className="pomodoro-toggle"
        aria-label={`Pomodoro timer, ${time}`}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        {time}
      </button>
      <div className={open ? 'pomodoro-controls open' : 'pomodoro-controls'}>
        <MinutesInput label="Study" value={durations.study} onChange={(study) => update({ study })} />
        <MinutesInput label="Rest" value={durations.rest} onChange={(rest) => update({ rest })} />
        <button
          type="button"
          className="button"
          onClick={() => {
            setOpen(false)
            setState(start(state, stamp(), durations))
          }}
        >
          Start
        </button>
      </div>
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
