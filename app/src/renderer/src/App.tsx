import { useState } from 'react'
import { AppHeader } from './AppHeader'
import { GeneratingScreen } from './generating/GeneratingScreen'
import { NewLessonScreen } from './generating/NewLessonScreen'
import { LessonScreen } from './lesson/LessonScreen'
import { LibraryScreen } from './library/LibraryScreen'
import { DayBarProvider } from './lesson/days/DayBar'
import { RestScreen } from './pomodoro/RestScreen'

type Screen =
  | { name: 'library'; folderId: number | null }
  | { name: 'new'; folderId: number | null; placeholder: { id: string; title: string } | null }
  | { name: 'generating'; lessonId: string }
  | { name: 'lesson'; lessonId: string }

export function App() {
  const [screen, setScreen] = useState<Screen>({ name: 'library', folderId: null })
  const [restTime, setRestTime] = useState<string | null>(null)
  const openLibrary = () => setScreen({ name: 'library', folderId: null })
  const openLesson = (lessonId: string) => setScreen({ name: 'lesson', lessonId })
  const openGenerating = (lessonId: string) => setScreen({ name: 'generating', lessonId })

  return (
    <DayBarProvider>
      <AppHeader onHome={openLibrary} onRest={setRestTime} resting={restTime !== null} />
      {restTime !== null && <RestScreen time={restTime} />}
      <main inert={restTime !== null}>
        {screen.name === 'library' && (
          <LibraryScreen
            onOpen={(lesson) => {
              if (lesson.status === 'ready') openLesson(lesson.id)
              else if (lesson.status === 'placeholder') {
                const placeholder = { id: lesson.id, title: lesson.title }
                setScreen({ name: 'new', folderId: lesson.folder_id, placeholder })
              } else openGenerating(lesson.id)
            }}
            onNew={(folderId) => setScreen({ name: 'new', folderId, placeholder: null })}
            folderId={screen.folderId}
            onFolder={(folderId) => setScreen({ name: 'library', folderId })}
          />
        )}
        {screen.name === 'new' && (
          <NewLessonScreen
            folderId={screen.folderId}
            placeholder={screen.placeholder}
            onCreated={openGenerating}
            onBack={() => setScreen({ name: 'library', folderId: screen.folderId })}
          />
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
