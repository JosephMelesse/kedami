import { Logo } from './Logo'
import { MusicPlayer } from './music/MusicPlayer'
import { PomodoroTimer } from './pomodoro/PomodoroTimer'

interface AppHeaderProps {
  onHome: () => void
  onRest: (time: string | null) => void
}

export function AppHeader({ onHome, onRest }: AppHeaderProps) {
  return (
    <header className="app-header">
      <button type="button" className="app-name" onClick={onHome}>
        <Logo />
        Kedami
      </button>
      <MusicPlayer />
      <PomodoroTimer onRest={onRest} />
    </header>
  )
}
