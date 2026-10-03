import { describe, expect, it } from 'vitest'
import { isAllowedRequest } from '../src/main/requests'

describe('isAllowedRequest', () => {
  it.each([
    'file:///home/me/kedami/app/out/renderer/index.html',
    'http://127.0.0.1:43211/lessons',
    'http://localhost:5173/src/main.tsx',
    'ws://localhost:5173/',
    'data:image/png;base64,AAAA',
    'blob:null/1234',
    'devtools://devtools/bundled/inspector.html'
  ])('allows %s', (url) => {
    expect(isAllowedRequest(url)).toBe(true)
  })

  it.each([
    'https://api.anthropic.com/v1/messages',
    'https://example.com/steal?token=x',
    'http://127.0.0.1.evil.com/',
    'http://localhost.evil.com/',
    'https://localhost/',
    'wss://localhost/',
    'http://192.168.1.5:8000/',
    'ftp://localhost/',
    'not a url'
  ])('blocks %s', (url) => {
    expect(isAllowedRequest(url)).toBe(false)
  })
})
