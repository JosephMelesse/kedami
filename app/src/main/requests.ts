// The renderer, including simulation frames, may only load local resources. The only outbound
// traffic is the server's calls to the Anthropic API, which don't pass through here.

const LOCAL_SCHEMES = new Set(['file:', 'data:', 'blob:', 'devtools:'])
const LOCAL_HOSTS = new Set(['127.0.0.1', 'localhost'])

export function isAllowedRequest(url: string): boolean {
  let parsed: URL
  try {
    parsed = new URL(url)
  } catch {
    return false
  }
  if (LOCAL_SCHEMES.has(parsed.protocol)) return true
  return ['http:', 'ws:'].includes(parsed.protocol) && LOCAL_HOSTS.has(parsed.hostname)
}
