// Calls to the local server. The base URL and session token come from the preload.
import type { Lesson } from './lesson/types'

export type LessonStatus = 'generating' | 'ready' | 'failed'

/** Who built a lesson: Claude Code, or the API pipeline Kedami no longer has. See architecture/agent-mode.md. */
export type Builder = 'pipeline' | 'agent'

export type MaterialRole = 'problem_set' | 'reference'

export interface Material {
  id: number
  filename: string
  role: MaterialRole
}

export interface LessonResponse {
  lesson: Lesson | null
  builder: Builder
  status: LessonStatus
  current_stage: number | null
  error: string | null
  materials: Material[]
  /** The block the student was last reading. */
  reading_block: string | null
  /** The blocks that begin day 2 onward, in lesson order. Empty if the lesson isn't split into days. */
  day_starts: string[]
}

export interface NewFile {
  file: File
  role: MaterialRole
}

export interface LessonSummary {
  id: string
  title: string
  subject: Lesson['subject']
  domain: Lesson['domain']
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
  builder: Builder
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

/** Save a new lesson's files. The server queues Claude Code's build of it at once. */
export async function createLesson(subject: Lesson['subject'], files: NewFile[], folderId: number | null): Promise<string> {
  const form = new FormData()
  form.append('subject', subject)
  if (folderId !== null) form.append('folder', String(folderId))
  for (const { file, role } of files) {
    form.append('files', file, file.name)
    form.append('roles', role)
  }
  const body = await request<{ id: string }>('POST', '/lessons', form)
  return body.id
}

/** End the build of a lesson Claude Code is building, stopping its job. */
export async function cancelLesson(lessonId: string): Promise<void> {
  await request('POST', `${lessonPath(lessonId)}/cancel`)
}

/** Work the server runs Claude Code for, one at a time. See architecture/agent-mode.md, Background jobs. */
export interface Job {
  id: number
  kind: 'build' | 'solution' | 'simulation'
  lesson_id: string
  block_id: string | null
  part_id: string | null
  status: 'queued' | 'running' | 'done' | 'failed' | 'canceled'
  error: string | null
}

export interface JobQueue {
  /** Whether Claude Code is on the path, so jobs can run at all. */
  claude: boolean
  running: Job | null
  queued: Job[]
}

export function getJobs(): Promise<JobQueue> {
  return request('GET', '/jobs')
}

/** Whether a lesson's build is queued behind another job, rather than starting. */
export function buildIsWaiting(queue: JobQueue | null, lessonId: string): boolean {
  if (!queue?.running) return false
  return queue.queued.some((job) => job.kind === 'build' && job.lesson_id === lessonId)
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

/** A problem part's step-by-step solution. Math and physics lines are bare LaTeX; general lines are Markdown. */
export type SolutionSteps =
  | { format: 'math'; method: string; steps: string[] }
  | { format: 'physics'; given: string[]; required: string[]; steps: string[] }
  | { format: 'general'; steps: string[] }

export interface SolutionResponse {
  /** Null until Claude Code has written it. */
  solution: SolutionSteps | null
  /** Whether its final answer matches the stored one; null when the answer isn't compared. */
  matches: boolean | null
}

/** A part's solution once Claude Code has written it; see architecture/agent-mode.md, Solutions and simulations. */
export function getSolution(lessonId: string, blockId: string, partId: string): Promise<SolutionResponse> {
  return request('GET', `${blockPath(lessonId, blockId)}/solution?part_id=${encodeURIComponent(partId)}`)
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

export async function renameLesson(lessonId: string, title: string): Promise<void> {
  await request('POST', `${lessonPath(lessonId)}/rename`, { title })
}

export async function moveLesson(lessonId: string, folderId: number | null): Promise<void> {
  await request('POST', `${lessonPath(lessonId)}/move`, { folder_id: folderId })
}

export async function setLessonActive(lessonId: string, active: boolean): Promise<void> {
  await request('POST', `${lessonPath(lessonId)}/active`, { active })
}

export async function deleteLesson(lessonId: string): Promise<void> {
  await request('DELETE', lessonPath(lessonId))
}
