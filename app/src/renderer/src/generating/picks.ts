// The DSA problem picker's text handling. See Picking problems in architecture/code-problems.md.

/** A picked problem. A null difficulty means it isn't in the imported dataset, so it is solved on LeetCode. */
export interface Pick {
  number: number
  title: string
  difficulty: string | null
}

/** Pasted or typed text split at commas and line breaks, each piece trimmed. */
export function pieces(text: string): string[] {
  return text
    .split(/[,\n]/)
    .map((piece) => piece.trim())
    .filter(Boolean)
}

/** "146", "#146", or "LeetCode 146" alone. */
export function bareNumber(piece: string): number | null {
  const match = /^(?:leetcode\s*)?#?\s*(\d{1,5})\.?$/i.exec(piece.trim())
  return match ? Number(match[1]) : null
}

/** A number followed by a title: "146 LRU Cache", "146. LRU Cache", "#146 - LRU Cache". */
export function numberAndTitle(piece: string): { number: number; title: string } | null {
  const match = /^(?:leetcode\s*)?#?\s*(\d{1,5})(?:\s*[.):-]\s*|\s+)(.*\S)$/i.exec(piece.trim())
  if (!match || !/[a-z0-9]/i.test(match[2])) return null
  return { number: Number(match[1]), title: match[2] }
}

/** The problem set the pipeline reads: one "1. Two Sum" per line, in the order picked. */
export function problemList(picks: Pick[]): string {
  return picks.map((pick) => `${pick.number}. ${pick.title}\n`).join('')
}

/** LeetCode's URL slug for a title, as the server makes it: "Pow(x, n)" is "powx-n". */
export function leetcodeSlug(title: string): string {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9 -]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
}
