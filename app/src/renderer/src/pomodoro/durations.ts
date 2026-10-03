// The study and rest durations, saved in the renderer's local storage.
import { DEFAULT_DURATIONS, type Durations, MAX_MINUTES, MIN_MINUTES } from './timer'

const KEY = 'kedami.pomodoro.durations'

function valid(value: unknown): value is number {
  return Number.isInteger(value) && (value as number) >= MIN_MINUTES && (value as number) <= MAX_MINUTES
}

export function loadDurations(storage: Storage = localStorage): Durations {
  try {
    const saved = JSON.parse(storage.getItem(KEY) ?? 'null')
    return {
      study: valid(saved?.study) ? saved.study : DEFAULT_DURATIONS.study,
      rest: valid(saved?.rest) ? saved.rest : DEFAULT_DURATIONS.rest
    }
  } catch {
    return DEFAULT_DURATIONS
  }
}

export function saveDurations(durations: Durations, storage: Storage = localStorage): void {
  try {
    storage.setItem(KEY, JSON.stringify(durations))
  } catch {
    // Unavailable storage only means the durations aren't remembered.
  }
}
