import { useDayBar } from './lesson/days/DayBar'
import { Logo } from './Logo'
import { MusicPlayer } from './music/MusicPlayer'
import { PomodoroTimer } from './pomodoro/PomodoroTimer'

interface AppHeaderProps {
  onHome: () => void
  onRest: (time: string | null) => void
  resting: boolean
}

export function AppHeader({ onHome, onRest, resting }: AppHeaderProps) {
  const bar = useDayBar()
  return (
    <header className="app-header">
      <button type="button" className="app-name" onClick={onHome}>
        <Logo />
        Kedami
      </button>
      <MusicPlayer resting={resting} bar={bar} />
      <PomodoroTimer onRest={onRest} />
    </header>
  )
}
