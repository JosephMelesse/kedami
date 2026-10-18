// A SQL chapter lesson's problem set. See In a lesson in architecture/sql-lessons.md.
import type { Recommendation } from '../api'

/** The problem set the server reads: "1. spider:{id} {question}" or "2. pgexercises:{path} {title}" per line. */
export function recommendedList(problems: Recommendation[]): string {
  return problems
    .map(
      (problem, index) => `${index + 1}. ${problem.source}:${problem.id} ${problem.text.replace(/\s+/g, ' ').trim()}\n`
    )
    .join('')
}
