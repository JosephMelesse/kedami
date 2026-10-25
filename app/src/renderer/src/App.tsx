import { useState } from 'react'
import { AppHeader } from './AppHeader'
import { GeneratingScreen } from './generating/GeneratingScreen'
import { NewLessonScreen } from './generating/NewLessonScreen'
import { LessonScreen } from './lesson/LessonScreen'
import { LibraryScreen } from './library/LibraryScreen'
import { DayBarProvider } from './lesson/days/DayBar'
import { RestScreen } from './pomodoro/RestScreen'
import { TerminalScreen } from './terminal/TerminalScreen'

type Screen =
  | { name: 'library'; folderId: number | null }
  | { name: 'new'; folderId: number | null }
  | { name: 'generating'; lessonId: string }
  | { name: 'lesson'; lessonId: string }

export function App() {
  const [screen, setScreen] = useState<Screen>({ name: 'library', folderId: null })
  const [restTime, setRestTime] = useState<string | null>(null)
  // The Terminal screen covers whatever screen is open, which keeps its state underneath.
  const [terminalOpen, setTerminalOpen] = useState(false)
  const openLibrary = () => {
    setTerminalOpen(false)
    setScreen({ name: 'library', folderId: null })
  }
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
      {/* The rest screen covers the terminal too, so the terminal's view is hidden while resting. */}
      {terminalOpen && restTime === null && <TerminalScreen />}
      <main inert={restTime !== null || terminalOpen}>
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
          <LessonScreen lessonId={screen.lessonId} onBack={openLibrary} onRerun={openGenerating} />
        )}
      </main>
    </DayBarProvider>
  )
}
