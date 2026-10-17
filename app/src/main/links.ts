// The only links the app opens outside itself, in the default browser: LeetCode problems and pgexercises
// pages. Each is checked here and its URL built here, so the renderer can only name a problem or a page.

const SLUG = /^[a-z0-9]+(-[a-z0-9]+)*$/
// One section folder and one page name, as in "joins/self2.html". Matches PAGE_PATH in sql_chapters.py.
const PAGE = /^[a-z]+\/[a-z0-9]+\.html$/

/** The problem's URL, or null if the slug isn't one LeetCode could have made. */
export function leetcodeProblemUrl(slug: unknown): string | null {
  if (typeof slug !== 'string' || slug.length > 200 || !SLUG.test(slug)) return null
  return `https://leetcode.com/problems/${slug}/`
}

/** The page's URL, or null if the path isn't a pgexercises section and page name. */
export function pgexercisesPageUrl(path: unknown): string | null {
  if (typeof path !== 'string' || path.length > 100 || !PAGE.test(path)) return null
  return `https://pgexercises.com/questions/${path}`
}
