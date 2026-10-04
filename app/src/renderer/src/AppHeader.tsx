import { Logo } from './Logo'
import { MusicPlayer } from './music/MusicPlayer'
import { PomodoroTimer } from './pomodoro/PomodoroTimer'

export function AppHeader({ onHome }: { onHome: () => void }) {
  return (
    <header className="app-header">
      <button type="button" className="app-name" onClick={onHome}>
        <Logo />
        Kedami
      </button>
      <MusicPlayer />
      <PomodoroTimer />
    </header>
  )
}
