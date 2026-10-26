import { useDayBar } from './lesson/days/DayBar'
import { Logo } from './Logo'
import { MusicPlayer } from './music/MusicPlayer'
import { PomodoroTimer } from './pomodoro/PomodoroTimer'

interface AppHeaderProps {
  onHome: () => void
  onRest: (time: string | null) => void
  resting: boolean
  terminalOpen: boolean
  onTerminal: () => void
}

export function AppHeader({ onHome, onRest, resting, terminalOpen, onTerminal }: AppHeaderProps) {
  const bar = useDayBar()
  return (
    <header className="app-header">
      <div className="app-start">
        <button type="button" className="app-name" onClick={onHome}>
          <Logo />
          Kedami
        </button>
        <button type="button" className="terminal-toggle" aria-pressed={terminalOpen} onClick={onTerminal}>
          Claude Code
        </button>
      </div>
      <MusicPlayer resting={resting} bar={bar} />
      <PomodoroTimer onRest={onRest} />
    </header>
  )
}
