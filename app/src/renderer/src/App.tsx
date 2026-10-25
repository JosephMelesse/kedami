import { useEffect, useLayoutEffect, useState } from 'react'
import { AppHeader } from './AppHeader'
import { GeneratingScreen } from './generating/GeneratingScreen'
import { NewLessonScreen } from './generating/NewLessonScreen'
import { LessonScreen } from './lesson/LessonScreen'
import { LibraryScreen } from './library/LibraryScreen'
import { DayBarProvider } from './lesson/days/DayBar'
import { RestScreen } from './pomodoro/RestScreen'
import { clampWidth, loadWidth, saveWidth } from './terminal/panelWidth'
import { TerminalPanel } from './terminal/TerminalPanel'
import { useNarrow } from './terminal/useNarrow'

type Screen =
  | { name: 'library'; folderId: number | null }
  | { name: 'new'; folderId: number | null }
  | { name: 'generating'; lessonId: string }
  | { name: 'lesson'; lessonId: string }

export function App() {
  const [screen, setScreen] = useState<Screen>({ name: 'library', folderId: null })
  const [restTime, setRestTime] = useState<string | null>(null)
  // The Terminal panel opens beside whatever screen is open; see architecture/agent-mode.md, Terminal panel.
  const [terminalOpen, setTerminalOpen] = useState(false)
  const [terminalWidth, setTerminalWidth] = useState(() => loadWidth(window.innerWidth))
  const narrow = useNarrow()
  // Beside the screen, the panel takes its width from it; in a narrow window it covers the screen instead.
  const beside = terminalOpen && !narrow
  const openLibrary = () => setScreen({ name: 'library', folderId: null })

  useEffect(() => window.kedami.onTerminalToggle(() => setTerminalOpen((open) => !open)), [])
  useEffect(() => saveWidth(terminalWidth), [terminalWidth])
  useEffect(() => {
    const fit = () => setTerminalWidth((width) => clampWidth(width, window.innerWidth))
    window.addEventListener('resize', fit)
    return () => window.removeEventListener('resize', fit)
  }, [])
  useLayoutEffect(() => {
    document.documentElement.style.setProperty('--terminal-width', beside ? `${terminalWidth}px` : '0px')
  }, [beside, terminalWidth])
  const openLesson = (lessonId: string) => setScreen({ name: 'lesson', lessonId })
  const openGenerating = (lessonId: string) => setScreen({ name: 'generating', lessonId })

  return (
    <DayBarProvider>
      <AppHeader
        onHome={openLibrary}
        onRest={setRestTime}
        resting={restTime !== null}
        terminalOpen={terminalOpen}
        onTerminal={() => setTerminalOpen((open) => !open)}
      />
      {restTime !== null && <RestScreen time={restTime} />}
      {/* The rest screen covers the panel too, so the terminal's view is hidden while resting. */}
      {terminalOpen && restTime === null && (
        <TerminalPanel width={terminalWidth} narrow={narrow} onWidth={setTerminalWidth} />
      )}
      <main inert={restTime !== null || (terminalOpen && narrow)}>
        {screen.name === 'library' && (
          <LibraryScreen
            onOpen={(lesson) => (lesson.status === 'ready' ? openLesson(lesson.id) : openGenerating(lesson.id))}
            onNew={(folderId) => setScreen({ name: 'new', folderId })}
            folderId={screen.folderId}
            onFolder={(folderId) => setScreen({ name: 'library', folderId })}
          />
        )}
        {screen.name === 'new' && (
          <NewLessonScreen folderId={screen.folderId} onCreated={openGenerating} onBack={openLibrary} />
        )}
        {screen.name === 'generating' && (
          <GeneratingScreen key={screen.lessonId} lessonId={screen.lessonId} onReady={openLesson} onBack={openLibrary} />
        )}
        {screen.name === 'lesson' && (
          <LessonScreen lessonId={screen.lessonId} onBack={openLibrary} />
        )}
      </main>
    </DayBarProvider>
  )
}
