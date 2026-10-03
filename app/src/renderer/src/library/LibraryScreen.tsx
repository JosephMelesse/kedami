import { useCallback, useEffect, useState } from 'react'
import {
  ApiError,
  createFolder,
  deleteFolder,
  deleteLesson,
  type Folder,
  type LessonSummary,
  listFolders,
  listLessons,
  moveLesson
} from '../api'
import { ConfirmDialog } from '../ConfirmDialog'
import { FolderTile } from './FolderTile'
import { LessonMenu } from './LessonMenu'
import { LessonTile } from './LessonTile'
import { NameDialog } from './NameDialog'
import { NewLessonTile } from './NewLessonTile'

type State =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; lessons: LessonSummary[]; folders: Folder[] }

type Dialog =
  | { kind: 'new-folder' }
  | { kind: 'delete-lesson'; lesson: LessonSummary }
  | { kind: 'delete-folder'; folder: Folder }

const POLL_MS = 3000

interface LibraryProps {
  onOpen: (lesson: LessonSummary) => void
  /** Start a new lesson in the given folder, or on the home page for null. */
  onNew: (folderId: number | null) => void
}

export function LibraryScreen({ onOpen, onNew }: LibraryProps) {
  const [state, setState] = useState<State>({ status: 'loading' })
  const [folderId, setFolderId] = useState<number | null>(null)
  const [dialog, setDialog] = useState<Dialog | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const generating = state.status === 'ready' && state.lessons.some((lesson) => lesson.status === 'generating')

  const load = useCallback(async () => {
    try {
      const [lessons, folders] = await Promise.all([listLessons(), listFolders()])
      setState({ status: 'ready', lessons, folders })
    } catch (error) {
      setState({ status: 'error', message: (error as Error).message })
    }
  }, [])

  useEffect(() => {
    load()
    // Refresh while a lesson is generating, so its tile shows when it is ready.
    const timer = generating ? setInterval(load, POLL_MS) : undefined
    return () => clearInterval(timer)
  }, [generating, load])

  const act = async (action: () => Promise<unknown>) => {
    setProblem(null)
    try {
      await action()
    } catch (error) {
      setProblem(error instanceof ApiError ? error.message : 'Could not reach the server.')
    }
    await load()
  }

  if (state.status === 'loading') return <p className="screen-message">Loading lessons</p>
  if (state.status === 'error') return <p className="screen-message">Could not load lessons: {state.message}</p>

  const folder = state.folders.find((f) => f.id === folderId) ?? null
  return (
    <>
      <LibraryView
        lessons={state.lessons}
        folders={state.folders}
        folder={folder}
        problem={problem}
        onOpen={onOpen}
        onNew={() => onNew(folder?.id ?? null)}
        onOpenFolder={(f) => setFolderId(f.id)}
        onHome={() => setFolderId(null)}
        onNewFolder={() => setDialog({ kind: 'new-folder' })}
        onDeleteFolder={(f) => setDialog({ kind: 'delete-folder', folder: f })}
        onMove={(lesson, target) => act(() => moveLesson(lesson.id, target))}
        onDelete={(lesson) => setDialog({ kind: 'delete-lesson', lesson })}
      />
      {dialog?.kind === 'new-folder' && (
        <NameDialog
          title="New folder"
          confirmLabel="Create"
          onCancel={() => setDialog(null)}
          onSubmit={async (name) => {
            try {
              await createFolder(name)
            } catch (error) {
              return error instanceof ApiError ? error.message : 'Could not reach the server.'
            }
            setDialog(null)
            await load()
            return null
          }}
        />
      )}
      {dialog?.kind === 'delete-lesson' && (
        <ConfirmDialog
          title={`Delete ${dialog.lesson.title}?`}
          body="Its files, progress, and simulations are removed for good."
          confirmLabel="Delete"
          destructive
          onCancel={() => setDialog(null)}
          onConfirm={() => {
            setDialog(null)
            act(() => deleteLesson(dialog.lesson.id))
          }}
        />
      )}
      {dialog?.kind === 'delete-folder' && (
        <ConfirmDialog
          title={`Delete ${dialog.folder.name}?`}
          body={
            dialog.folder.lessons === 0
              ? 'The folder is empty.'
              : `Its ${dialog.folder.lessons === 1 ? 'lesson moves' : `${dialog.folder.lessons} lessons move`} back to Lessons.`
          }
          confirmLabel="Delete folder"
          destructive
          onCancel={() => setDialog(null)}
          onConfirm={() => {
            setDialog(null)
            setFolderId(null)
            act(() => deleteFolder(dialog.folder.id))
          }}
        />
      )}
    </>
  )
}

interface LibraryViewProps {
  lessons: LessonSummary[]
  folders: Folder[]
  /** The open folder, or null for the home page. */
  folder: Folder | null
  problem: string | null
  onOpen: (lesson: LessonSummary) => void
  onNew: () => void
  onOpenFolder: (folder: Folder) => void
  onHome: () => void
  onNewFolder: () => void
  onDeleteFolder: (folder: Folder) => void
  onMove: (lesson: LessonSummary, folderId: number | null) => void
  onDelete: (lesson: LessonSummary) => void
}

/** Home shows folders, then the lessons in no folder, then the new lesson tile. A folder shows its lessons. */
export function LibraryView(props: LibraryViewProps) {
  const { lessons, folders, folder, problem } = props
  const shown = lessons.filter((lesson) => lesson.folder_id === (folder?.id ?? null))

  return (
    <div className="library">
      {folder && (
        <nav className="library-nav">
          <button type="button" className="link-button" onClick={props.onHome}>
            Lessons
          </button>
        </nav>
      )}
      <header className="library-header">
        <h1>{folder ? folder.name : 'Lessons'}</h1>
        {folder ? (
          <button type="button" className="button" onClick={() => props.onDeleteFolder(folder)}>
            Delete folder
          </button>
        ) : (
          <button type="button" className="button" onClick={props.onNewFolder}>
            New folder
          </button>
        )}
      </header>
      {problem && <p className="answer-error">{problem}</p>}
      <ul className="tile-grid">
        {!folder &&
          folders.map((f) => (
            <li key={`folder-${f.id}`}>
              <FolderTile folder={f} onOpen={() => props.onOpenFolder(f)} />
            </li>
          ))}
        {shown.map((lesson) => (
          <li key={lesson.id} className="tile-wrap">
            <LessonTile lesson={lesson} onOpen={() => props.onOpen(lesson)} />
            <LessonMenu
              lesson={lesson}
              folders={folders}
              onMove={(target) => props.onMove(lesson, target)}
              onDelete={() => props.onDelete(lesson)}
            />
          </li>
        ))}
        <li>
          <NewLessonTile onClick={props.onNew} />
        </li>
      </ul>
    </div>
  )
}
