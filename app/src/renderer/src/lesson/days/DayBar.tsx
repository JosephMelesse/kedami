import { createContext, type ReactNode, useContext, useState } from 'react'

/** The finish-line progress shown behind the music player while a lesson is open. */
export interface DayBar {
  fill: number
  /** Whether "Done for today" is showing. */
  note: boolean
}

type SetDayBar = (bar: DayBar | null) => void

const BarContext = createContext<DayBar | null>(null)
const SetBarContext = createContext<SetDayBar>(() => {})

/**
 * Holds the bar apart from the screens, so a scroll re-renders only what reads it, not the lesson.
 * The lesson sets it, and the app header reads it.
 */
export function DayBarProvider({ children }: { children: ReactNode }) {
  const [bar, setBar] = useState<DayBar | null>(null)
  return (
    <SetBarContext.Provider value={setBar}>
      <BarContext.Provider value={bar}>{children}</BarContext.Provider>
    </SetBarContext.Provider>
  )
}

export const useDayBar = () => useContext(BarContext)
export const useSetDayBar = () => useContext(SetBarContext)
