// Calls to the local server. The base URL and session token come from the preload.
import type { Lesson } from './lesson/types'

export interface LessonResponse {
  lesson: Lesson
  status: string
  current_stage: number | null
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

export function getLesson(lessonId: string): Promise<LessonResponse> {
  return get(`/lessons/${encodeURIComponent(lessonId)}`)
}

export async function getPlotPoints(lessonId: string, blockId: string): Promise<PlotSeries[]> {
  const path = `/lessons/${encodeURIComponent(lessonId)}/blocks/${encodeURIComponent(blockId)}/points`
  const body = await get<{ functions: PlotSeries[] }>(path)
  return body.functions
}
