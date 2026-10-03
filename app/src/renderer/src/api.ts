// Calls to the local server. The base URL and session token come from the preload.
import type { Lesson } from './lesson/types'

export type LessonStatus = 'generating' | 'ready' | 'failed'

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
}

export interface NewFile {
  file: File
  role: MaterialRole
  force: boolean
}

export interface LessonSummary {
  id: string
  title: string
  subject: Lesson['subject']
  status: LessonStatus
  current_stage: number | null
  error: string | null
  /** Null when the lesson is on the home page. */
  folder_id: number | null
  created: string
  problems_total: number
  problems_done: number
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

export async function createLesson(subject: Lesson['subject'], files: NewFile[], folderId: number | null): Promise<string> {
  const form = new FormData()
  form.append('subject', subject)
  if (folderId !== null) form.append('folder', String(folderId))
  for (const { file, role, force } of files) {
    form.append('files', file, file.name)
    form.append('roles', role)
    form.append('force', String(force))
  }
  const body = await request<{ id: string }>('POST', '/lessons', form)
  return body.id
}

export async function rerunLesson(lessonId: string, stage: number, force: Record<number, boolean>): Promise<void> {
  await request('POST', `${lessonPath(lessonId)}/rerun`, { stage, force })
}

export function getLesson(lessonId: string): Promise<LessonResponse> {
  return request('GET', lessonPath(lessonId))
}

export async function getPlotPoints(lessonId: string, blockId: string): Promise<PlotSeries[]> {
  const body = await request<{ functions: PlotSeries[] }>('GET', `${blockPath(lessonId, blockId)}/points`)
  return body.functions
}

export async function getProgress(lessonId: string): Promise<ProgressRecord[]> {
  const body = await request<{ progress: ProgressRecord[] }>('GET', `${lessonPath(lessonId)}/progress`)
  return body.progress
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

export interface Folder {
  id: number
  name: string
  /** How many lessons it holds. */
  lessons: number
}

export async function listFolders(): Promise<Folder[]> {
  const body = await request<{ folders: Folder[] }>('GET', '/folders')
  return body.folders
}

export function createFolder(name: string): Promise<Folder> {
  return request('POST', '/folders', { name })
}

export async function renameFolder(folderId: number, name: string): Promise<void> {
  await request('POST', `/folders/${folderId}/rename`, { name })
}

export async function deleteFolder(folderId: number): Promise<void> {
  await request('DELETE', `/folders/${folderId}`)
}

export async function moveLesson(lessonId: string, folderId: number | null): Promise<void> {
  await request('POST', `${lessonPath(lessonId)}/move`, { folder_id: folderId })
}

export async function deleteLesson(lessonId: string): Promise<void> {
  await request('DELETE', lessonPath(lessonId))
}
