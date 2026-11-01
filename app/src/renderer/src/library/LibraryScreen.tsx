import { Fragment, useCallback, useEffect, useState } from 'react'
import {
  ApiError,
  createFolder,
  deleteFolder,
  deleteLesson,
  type Folder,
  type LessonSummary,
  listFolders,
  listLessons,
  moveFolder,
  moveLesson,
  renameFolder,
  renameLesson,
  setLessonActive
} from '../api'
import { ConfirmDialog } from '../ConfirmDialog'
import { ActiveLessons } from './ActiveLessons'
import { deleteSummary, foldersAbove, moveTargets } from './folders'
import { FolderNote } from './FolderNote'
import { FolderTile } from './FolderTile'
import { LessonMenu } from './LessonMenu'
import { LessonTile } from './LessonTile'
import { MoveDialog } from './MoveDialog'
import { NameDialog } from './NameDialog'
import { NewLessonTile } from './NewLessonTile'

type State =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; lessons: LessonSummary[]; folders: Folder[] }

type Dialog =
  | { kind: 'new-folder' }
  | { kind: 'rename-lesson'; lesson: LessonSummary }
  | { kind: 'move-lesson'; lesson: LessonSummary }
  | { kind: 'delete-lesson'; lesson: LessonSummary }
  | { kind: 'rename-folder'; folder: Folder }
  | { kind: 'move-folder'; folder: Folder }
  | { kind: 'delete-folder'; folder: Folder }

const POLL_MS = 3000

interface LibraryProps {
  onOpen: (lesson: LessonSummary) => void
  /** Start a new lesson in the given folder, or on the home page for null. */
  onNew: (folderId: number | null) => void
  /** The open folder, or null for the home page. Kept by the app so the header can always go home. */
  folderId: number | null
  onFolder: (folderId: number | null) => void
}

export function LibraryScreen({ onOpen, onNew, folderId, onFolder }: LibraryProps) {
  const [state, setState] = useState<State>({ status: 'loading' })
  const [dialog, setDialog] = useState<Dialog | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  // Shown only on the page it is about, so it doesn't follow the student around.
  const [notice, setNotice] = useState<{ folderId: number | null; text: string } | null>(null)
  // Notes typed since this screen opened. They win over a refresh that may have been read before the save landed.
  const [typedNotes, setTypedNotes] = useState<Record<number, string>>({})
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
    setNotice(null)
    try {
      await action()
    } catch (error) {
      setProblem(error instanceof ApiError ? error.message : 'Could not reach the server.')
    }
    await load()
  }

  /** Run a naming action from a dialog; resolves to an error to show in it, or closes it. */
  const named = async (action: () => Promise<unknown>): Promise<string | null> => {
    try {
      await action()
    } catch (error) {
      return error instanceof ApiError ? error.message : 'Could not reach the server.'
    }
    setDialog(null)
    await load()
    return null
  }

  if (state.status === 'loading') return <p className="screen-message">Loading lessons</p>
  if (state.status === 'error') return <p className="screen-message">Could not load lessons: {state.message}</p>

  const folders = state.folders.map((f) => (f.id in typedNotes ? { ...f, note: typedNotes[f.id] } : f))
  const folder = folders.find((f) => f.id === folderId) ?? null
  const parentName = (f: Folder) => folders.find((other) => other.id === f.parent_id)?.name ?? 'Lessons'
  return (
    <>
      <LibraryView
        lessons={state.lessons}
        folders={folders}
        folder={folder}
        problem={problem}
        notice={notice?.folderId === folderId ? notice.text : null}
        onOpen={onOpen}
        onNew={() => onNew(folder?.id ?? null)}
        onOpenFolder={(f) => onFolder(f.id)}
        onHome={() => onFolder(null)}
        onNewFolder={() => setDialog({ kind: 'new-folder' })}
        onRenameFolder={(f) => setDialog({ kind: 'rename-folder', folder: f })}
        onMoveFolder={(f) => setDialog({ kind: 'move-folder', folder: f })}
        onDeleteFolder={(f) => setDialog({ kind: 'delete-folder', folder: f })}
        onRename={(lesson) => setDialog({ kind: 'rename-lesson', lesson })}
        onMove={(lesson) => setDialog({ kind: 'move-lesson', lesson })}
        onSetActive={(lesson, active) => act(() => setLessonActive(lesson.id, active))}
        onDelete={(lesson) => setDialog({ kind: 'delete-lesson', lesson })}
        onNoteChange={(f, note) => setTypedNotes((typed) => ({ ...typed, [f.id]: note }))}
      />
      {dialog?.kind === 'new-folder' && (
        <NameDialog
          title="New folder"
          confirmLabel="Create"
          onCancel={() => setDialog(null)}
          onSubmit={(name) => named(() => createFolder(name, folder?.id ?? null))}
        />
      )}
      {dialog?.kind === 'rename-folder' && (
        <NameDialog
          title="Rename folder"
          confirmLabel="Rename"
          initial={dialog.folder.name}
          onCancel={() => setDialog(null)}
          onSubmit={(name) => named(() => renameFolder(dialog.folder.id, name))}
        />
      )}
      {dialog?.kind === 'move-folder' && (
        <MoveDialog
          title={`Move ${dialog.folder.name}`}
          targets={moveTargets(folders, dialog.folder.parent_id, dialog.folder.id)}
          onCancel={() => setDialog(null)}
          onPick={(target) => named(() => moveFolder(dialog.folder.id, target))}
        />
      )}
      {dialog?.kind === 'move-lesson' && (
        <MoveDialog
          title={`Move ${dialog.lesson.title}`}
          targets={moveTargets(folders, dialog.lesson.folder_id)}
          onCancel={() => setDialog(null)}
          onPick={(target) => named(() => moveLesson(dialog.lesson.id, target))}
        />
      )}
      {dialog?.kind === 'rename-lesson' && (
        <NameDialog
          title="Rename lesson"
          confirmLabel="Rename"
          initial={dialog.lesson.title}
          maxLength={120}
          onCancel={() => setDialog(null)}
          onSubmit={(name) => named(() => renameLesson(dialog.lesson.id, name))}
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
          body={deleteSummary(folders.find((f) => f.id === dialog.folder.id) ?? dialog.folder, parentName(dialog.folder))}
          confirmLabel="Delete folder"
          destructive
          onCancel={() => setDialog(null)}
          onConfirm={() => {
            setDialog(null)
            act(async () => {
              const deleted = await deleteFolder(dialog.folder.id)
              onFolder(deleted.parent_id)
              if (deleted.renamed.length > 0) {
                const names = deleted.renamed.map((f) => `${f.old} is now ${f.new}`).join(', ')
                setNotice({ folderId: deleted.parent_id, text: `${names}, since that name was taken.` })
              }
            })
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
  notice: string | null
  onOpen: (lesson: LessonSummary) => void
  onNew: () => void
  onOpenFolder: (folder: Folder) => void
  onHome: () => void
  onNewFolder: () => void
  onRenameFolder: (folder: Folder) => void
  onMoveFolder: (folder: Folder) => void
  onDeleteFolder: (folder: Folder) => void
  onRename: (lesson: LessonSummary) => void
  onMove: (lesson: LessonSummary) => void
  onSetActive: (lesson: LessonSummary, active: boolean) => void
  onDelete: (lesson: LessonSummary) => void
  onNoteChange: (folder: Folder, note: string) => void
}

/** Home shows the active lessons, then the top-level folders, then the lessons in no folder, then the new lesson tile. A folder shows the same below a breadcrumb, without the active lessons. */
export function LibraryView(props: LibraryViewProps) {
  const { lessons, folders, folder, problem, notice } = props
  const here = folder?.id ?? null
  const shown = lessons.filter((lesson) => lesson.folder_id === here)
  const subfolders = folders.filter((f) => f.parent_id === here)

  return (
    <div className="library">
      {folder && (
        <nav className="library-nav">
          <button type="button" className="link-button" onClick={props.onHome}>
            Lessons
          </button>
          {foldersAbove(folders, folder).map((above) => (
            <Fragment key={above.id}>
              <span className="muted"> / </span>
              <button type="button" className="link-button" onClick={() => props.onOpenFolder(above)}>
                {above.name}
              </button>
            </Fragment>
          ))}
        </nav>
      )}
      <header className="library-header">
        <h1>{folder ? folder.name : 'Lessons'}</h1>
        {folder ? (
          <div className="library-actions">
            <button type="button" className="button" onClick={props.onNewFolder}>
              New folder
            </button>
            <button type="button" className="button" onClick={() => props.onRenameFolder(folder)}>
              Rename
            </button>
            <button type="button" className="button" onClick={() => props.onMoveFolder(folder)}>
              Move
            </button>
            <button type="button" className="button" onClick={() => props.onDeleteFolder(folder)}>
              Delete folder
            </button>
          </div>
        ) : (
          <button type="button" className="button" onClick={props.onNewFolder}>
            New folder
          </button>
        )}
      </header>
      {problem && <p className="answer-error">{problem}</p>}
      {notice && <p className="muted library-notice">{notice}</p>}
      {!folder && <ActiveLessons lessons={lessons} onOpen={props.onOpen} />}
      {folder && (
        <FolderNote
          key={folder.id}
          folderId={folder.id}
          initial={folder.note}
          onChange={(note) => props.onNoteChange(folder, note)}
        />
      )}
      <ul className="tile-grid">
        {subfolders.map((f) => (
          <li key={`folder-${f.id}`}>
            <FolderTile folder={f} onOpen={() => props.onOpenFolder(f)} />
          </li>
        ))}
        {shown.map((lesson) => (
          <li key={lesson.id} className="tile-wrap">
            <LessonTile lesson={lesson} onOpen={() => props.onOpen(lesson)} />
            <div className="tile-corner">
              {lesson.status === 'ready' && (
                <label className="tile-active">
                  <input
                    type="checkbox"
                    checked={lesson.active}
                    aria-label={`Active: ${lesson.title}`}
                    onChange={(event) => props.onSetActive(lesson, event.target.checked)}
                  />
                  Active
                </label>
              )}
              <LessonMenu
                lesson={lesson}
                folders={folders}
                onRename={() => props.onRename(lesson)}
                onMove={() => props.onMove(lesson)}
                onDelete={() => props.onDelete(lesson)}
              />
            </div>
          </li>
        ))}
        <li>
          <NewLessonTile onClick={props.onNew} />
        </li>
      </ul>
    </div>
  )
}
