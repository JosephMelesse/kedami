import { AppHeader } from './AppHeader'
import { LessonScreen } from './lesson/LessonScreen'

// Until the Library screen exists, the app opens the hand-written sample lesson.
const SAMPLE_LESSON_ID = 'sample'

export function App() {
  return (
    <>
      <AppHeader />
      <main>
        <LessonScreen lessonId={SAMPLE_LESSON_ID} />
      </main>
    </>
  )
}
