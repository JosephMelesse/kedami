// The only links the app opens outside itself: LeetCode problems, in the default browser.

const SLUG = /^[a-z0-9]+(-[a-z0-9]+)*$/

/** The problem's URL, or null if the slug isn't one LeetCode could have made. */
export function leetcodeProblemUrl(slug: unknown): string | null {
  if (typeof slug !== 'string' || slug.length > 200 || !SLUG.test(slug)) return null
  return `https://leetcode.com/problems/${slug}/`
}
