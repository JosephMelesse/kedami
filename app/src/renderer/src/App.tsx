import { useState } from 'react'
import { AppHeader } from './AppHeader'
import { GeneratingScreen } from './generating/GeneratingScreen'
import { NewLessonScreen } from './generating/NewLessonScreen'
import { LessonScreen } from './lesson/LessonScreen'
import { LibraryScreen } from './library/LibraryScreen'
import { RestScreen } from './pomodoro/RestScreen'

type Screen =
  | { name: 'library' }
  | { name: 'new'; folderId: number | null }
  | { name: 'generating'; lessonId: string }
  | { name: 'lesson'; lessonId: string }

export function App() {
  const [screen, setScreen] = useState<Screen>({ name: 'library' })
  const [restTime, setRestTime] = useState<string | null>(null)
  const openLibrary = () => setScreen({ name: 'library' })
  const openLesson = (lessonId: string) => setScreen({ name: 'lesson', lessonId })
  const openGenerating = (lessonId: string) => setScreen({ name: 'generating', lessonId })

  return (
    <>
      <AppHeader onHome={openLibrary} onRest={setRestTime} resting={restTime !== null} />
      {restTime !== null && <RestScreen time={restTime} />}
      <main inert={restTime !== null}>
        {screen.name === 'library' && (
          <LibraryScreen
            onOpen={(lesson) => (lesson.status === 'ready' ? openLesson(lesson.id) : openGenerating(lesson.id))}
            onNew={(folderId) => setScreen({ name: 'new', folderId })}
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
    </>
  )
}
