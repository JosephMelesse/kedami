// Calls to the local server. The base URL and session token come from the preload.
import type { Lesson } from './lesson/types'

export type LessonStatus = 'generating' | 'ready' | 'failed'

export interface LessonResponse {
  lesson: Lesson | null
  status: LessonStatus
  current_stage: number | null
}

export interface LessonSummary {
  id: string
  title: string
  subject: Lesson['subject']
  status: LessonStatus
  current_stage: number | null
  created: string
  problems_total: number
  problems_done: number
}

export interface PlotSeries {
  label: string
  points: [number, number | null][]
}

async function get<T>(path: string): Promise<T> {
  const { baseUrl, token } = await window.kedami.serverConnection()
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`)
  }
  return response.json() as Promise<T>
}

export async function listLessons(): Promise<LessonSummary[]> {
  const body = await get<{ lessons: LessonSummary[] }>('/lessons')
  return body.lessons
}

export function getLesson(lessonId: string): Promise<LessonResponse> {
  return get(`/lessons/${encodeURIComponent(lessonId)}`)
}

export async function getPlotPoints(lessonId: string, blockId: string): Promise<PlotSeries[]> {
  const path = `/lessons/${encodeURIComponent(lessonId)}/blocks/${encodeURIComponent(blockId)}/points`
  const body = await get<{ functions: PlotSeries[] }>(path)
  return body.functions
}
