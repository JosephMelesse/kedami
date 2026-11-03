// Calls to the local server. The base URL and session token come from the preload.
import type { Lesson } from './lesson/types'

export type LessonStatus = 'placeholder' | 'generating' | 'ready' | 'failed'

export type MaterialRole = 'problem_set' | 'reference'

export interface Material {
  id: number
  filename: string
  role: MaterialRole
  force_transcription: boolean
}

export interface LessonResponse {
  lesson: Lesson | null
  status: LessonStatus
  current_stage: number | null
  error: string | null
  materials: Material[]
  /** Stages a rerun can start from. Empty if the lesson can't be rerun. */
  rerun_stages: number[]
  /** The block the student was last reading, which may be gone after a rerun. */
  reading_block: string | null
  /** The blocks that begin day 2 onward, in lesson order. Empty if the lesson isn't split into days. */
  day_starts: string[]
}

export interface NewFile {
  file: File
  role: MaterialRole
  force: boolean
}

export interface LessonSummary {
  id: string
  title: string
  /** Null only on a placeholder. */
  subject: Lesson['subject'] | null
  status: LessonStatus
  current_stage: number | null
  error: string | null
  /** Null when the lesson is on the home page. */
  folder_id: number | null
  created: string
  problems_total: number
  problems_done: number
  /** Shown in the home page's Active card. */
  active: boolean
  /** As YYYY-MM-DD, or null with none. */
  due_date: string | null
  /** Every problem is done, also while a rerun is under way. */
  done: boolean
  overdue: boolean
}

export type TreeNode =
  | { num: number | null }
  | { sym: string }
  | { add: TreeNode[] }
  | { mul: TreeNode[] }
  | { pow: [TreeNode, TreeNode] }
  | { fn: string; arg: TreeNode }

export interface PlotSeries {
  label: string
  points: [number, number | null][]
  tree: TreeNode
}

export type ProgressStatus = 'not_started' | 'in_progress' | 'correct' | 'marked_done'

export interface ProgressRecord {
  block_id: string
  part_id: string | null
  status: ProgressStatus
  last_response: unknown
  attempts: number
  hints_used: number
  updated: string | null
}

/** A failed request. The message is the server's explanation, fit to show the student. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string
  ) {
    super(message)
  }
}

async function request<T>(method: 'GET' | 'POST' | 'DELETE', path: string, body?: unknown): Promise<T> {
  const { baseUrl, token } = await window.kedami.serverConnection()
  // A FormData body sets its own multipart content type, with the boundary.
  const form = body instanceof FormData
  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body === undefined || form ? {} : { 'Content-Type': 'application/json' })
    },
    body: body === undefined ? undefined : form ? body : JSON.stringify(body)
  })
  if (!response.ok) {
    const detail = await response.json().then((json) => json.detail, () => null)
    throw new ApiError(response.status, typeof detail === 'string' ? detail : `${response.status} ${response.statusText}`)
  }
  return response.json() as Promise<T>
}

const lessonPath = (lessonId: string) => `/lessons/${encodeURIComponent(lessonId)}`
const blockPath = (lessonId: string, blockId: string) => `${lessonPath(lessonId)}/blocks/${encodeURIComponent(blockId)}`

export async function listLessons(): Promise<LessonSummary[]> {
  const body = await request<{ lessons: LessonSummary[] }>('GET', '/lessons')
  return body.lessons
}

function lessonForm(subject: Lesson['subject'], files: NewFile[]): FormData {
  const form = new FormData()
  form.append('subject', subject)
  for (const { file, role, force } of files) {
    form.append('files', file, file.name)
    form.append('roles', role)
    form.append('force', String(force))
  }
  return form
}

export async function createLesson(
  subject: Lesson['subject'],
  files: NewFile[],
  folderId: number | null
): Promise<string> {
  const form = lessonForm(subject, files)
  if (folderId !== null) form.append('folder', String(folderId))
  const body = await request<{ id: string }>('POST', '/lessons', form)
  return body.id
}

/** Upload a placeholder's material. It keeps its ID, name, folder, and due date, and starts generating. */
export async function fillPlaceholder(
  lessonId: string,
  subject: Lesson['subject'],
  files: NewFile[]
): Promise<string> {
  const body = await request<{ id: string }>('POST', `${lessonPath(lessonId)}/fill`, lessonForm(subject, files))
  return body.id
}

export interface PlannedLesson {
  name: string
  /** As YYYY-MM-DD. */
  due_date: string | null
}

export interface ListProblem {
  /** 1 for the first line, or 0 for the list as a whole. */
  line: number
  text: string
  reason: string
}

/** Read a pasted list on the server, saving nothing. One bad line rejects the whole list. */
export function parsePlaceholderList(text: string): Promise<{ placeholders: PlannedLesson[]; problems: ListProblem[] }> {
  return request('POST', '/placeholders/parse', { text })
}

export async function createPlaceholders(folderId: number | null, placeholders: PlannedLesson[]): Promise<void> {
  await request('POST', '/placeholders', { folder_id: folderId, placeholders })
}

export async function rerunLesson(lessonId: string, stage: number, force: Record<number, boolean>): Promise<void> {
  await request('POST', `${lessonPath(lessonId)}/rerun`, { stage, force })
}

export function getLesson(lessonId: string): Promise<LessonResponse> {
  return request('GET', lessonPath(lessonId))
}

export async function saveReadingPosition(lessonId: string, blockId: string): Promise<void> {
  await request('POST', `${lessonPath(lessonId)}/reading-position`, { block_id: blockId })
}

export async function saveDays(lessonId: string, blockIds: string[]): Promise<void> {
  await request('POST', `${lessonPath(lessonId)}/days`, { block_ids: blockIds })
}

export async function getPlotPoints(lessonId: string, blockId: string): Promise<PlotSeries[]> {
  const body = await request<{ functions: PlotSeries[] }>('GET', `${blockPath(lessonId, blockId)}/points`)
  return body.functions
}

export function getProgress(lessonId: string): Promise<{ progress: ProgressRecord[] }> {
  return request('GET', `${lessonPath(lessonId)}/progress`)
}

export function checkResponse(
  lessonId: string,
  blockId: string,
  partId: string | null,
  response: unknown
): Promise<{ correct: boolean; progress: ProgressRecord }> {
  return request('POST', `${blockPath(lessonId, blockId)}/check`, { part_id: partId, response })
}

export async function revealHints(
  lessonId: string,
  blockId: string,
  partId: string | null,
  count: number
): Promise<ProgressRecord> {
  const body = await request<{ progress: ProgressRecord }>('POST', `${blockPath(lessonId, blockId)}/hint`, {
    part_id: partId,
    count
  })
  return body.progress
}

export async function markDone(lessonId: string, blockId: string, partId: string, done: boolean): Promise<ProgressRecord> {
  const body = await request<{ progress: ProgressRecord }>('POST', `${blockPath(lessonId, blockId)}/mark-done`, {
    part_id: partId,
    done
  })
  return body.progress
}

export interface SimulationState {
  code: string
  flagged: boolean
  error: string | null
}

export function getSimulation(lessonId: string, blockId: string): Promise<SimulationState> {
  return request('GET', `${blockPath(lessonId, blockId)}/simulation`)
}

export async function reportSimulation(lessonId: string, blockId: string, ok: boolean, error: string | null): Promise<void> {
  await request('POST', `${blockPath(lessonId, blockId)}/simulation-status`, { ok, error })
}

export function regenerateSimulation(lessonId: string, blockId: string): Promise<SimulationState> {
  return request('POST', `${blockPath(lessonId, blockId)}/regenerate`)
}

/** A problem part's step-by-step solution. Math and physics lines are bare LaTeX; general lines are Markdown. */
export type SolutionSteps =
  | { format: 'math'; method: string; steps: string[] }
  | { format: 'physics'; given: string[]; required: string[]; steps: string[] }
  | { format: 'general'; steps: string[] }

export interface SolutionResponse {
  solution: SolutionSteps
  /** Whether its final answer matches the stored one; null when the answer isn't compared. */
  matches: boolean | null
}

/** The stored solution, or one written now; the first request for a part waits on the model. */
export function getSolution(lessonId: string, blockId: string, partId: string): Promise<SolutionResponse> {
  return request('POST', `${blockPath(lessonId, blockId)}/solution`, { part_id: partId })
}

export interface Folder {
  id: number
  name: string
  /** Null at the top level. */
  parent_id: number | null
  /** How many lessons it holds, counting those in its subfolders at any depth. */
  lessons: number
  /** How many lessons sit directly in it. */
  own_lessons: number
  /** How many folders sit directly in it. */
  subfolders: number
  /** The student's own text, never sent to the model. */
  note: string
  /** The soonest due date among unfinished lessons inside it, including subfolders, as YYYY-MM-DD. */
  next_due: string | null
  next_due_overdue: boolean
}

export interface DeletedFolder {
  /** Where its contents went, or null for the home page. */
  parent_id: number | null
  /** Subfolders given a number because their name was taken there. */
  renamed: { id: number; old: string; new: string }[]
}

export async function listFolders(): Promise<Folder[]> {
  const body = await request<{ folders: Folder[] }>('GET', '/folders')
  return body.folders
}

export function createFolder(name: string, parentId: number | null): Promise<Folder> {
  return request('POST', '/folders', { name, parent_id: parentId })
}

export async function renameFolder(folderId: number, name: string): Promise<void> {
  await request('POST', `/folders/${folderId}/rename`, { name })
}

export async function saveFolderNote(folderId: number, note: string): Promise<void> {
  await request('POST', `/folders/${folderId}/note`, { note })
}

export async function moveFolder(folderId: number, parentId: number | null): Promise<void> {
  await request('POST', `/folders/${folderId}/move`, { parent_id: parentId })
}

export function deleteFolder(folderId: number): Promise<DeletedFolder> {
  return request('DELETE', `/folders/${folderId}`)
}

export async function renameLesson(lessonId: string, title: string): Promise<void> {
  await request('POST', `${lessonPath(lessonId)}/rename`, { title })
}

export async function moveLesson(lessonId: string, folderId: number | null): Promise<void> {
  await request('POST', `${lessonPath(lessonId)}/move`, { folder_id: folderId })
}

export async function setLessonDueDate(lessonId: string, dueDate: string | null): Promise<void> {
  await request('POST', `${lessonPath(lessonId)}/due-date`, { due_date: dueDate })
}

export async function setLessonActive(lessonId: string, active: boolean): Promise<void> {
  await request('POST', `${lessonPath(lessonId)}/active`, { active })
}

export async function deleteLesson(lessonId: string): Promise<void> {
  await request('DELETE', lessonPath(lessonId))
}
