// Calls to the local server. The base URL and session token come from the preload.
import type { Lesson } from './lesson/types'

export type LessonStatus = 'generating' | 'ready' | 'failed'

export interface LessonResponse {
  lesson: Lesson | null
  status: LessonStatus
  current_stage: number | null
  error: string | null
}

export interface LessonSummary {
  id: string
  title: string
  subject: Lesson['subject']
  status: LessonStatus
  current_stage: number | null
  error: string | null
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

async function request<T>(method: 'GET' | 'POST', path: string, body?: unknown): Promise<T> {
  const { baseUrl, token } = await window.kedami.serverConnection()
  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' })
    },
    body: body === undefined ? undefined : JSON.stringify(body)
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

export async function createLesson(subject: Lesson['subject'], problemSet: string, reference: string): Promise<string> {
  const body = await request<{ id: string }>('POST', '/lessons', { subject, problem_set: problemSet, reference })
  return body.id
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
