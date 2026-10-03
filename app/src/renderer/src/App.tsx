import { useState } from 'react'
import { AppHeader } from './AppHeader'
import { LessonScreen } from './lesson/LessonScreen'
import { LibraryScreen } from './library/LibraryScreen'

type Screen = { name: 'library' } | { name: 'lesson'; lessonId: string }

export function App() {
  const [screen, setScreen] = useState<Screen>({ name: 'library' })
  const openLibrary = () => setScreen({ name: 'library' })

  return (
    <>
      <AppHeader onHome={openLibrary} />
      <main>
        {screen.name === 'library' ? (
          <LibraryScreen onOpen={(lessonId) => setScreen({ name: 'lesson', lessonId })} />
        ) : (
          <LessonScreen lessonId={screen.lessonId} onBack={openLibrary} />
        )}
      </main>
    </>
  )
}
