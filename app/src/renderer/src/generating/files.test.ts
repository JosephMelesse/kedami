import { describe, expect, it } from 'vitest'
import { canForce, kindOf } from './files'

describe('kindOf', () => {
  it('recognizes supported files, ignoring case', () => {
    expect(kindOf('ps3.PDF')).toBe('pdf')
    expect(kindOf('scan.jpeg')).toBe('image')
    expect(kindOf('notes.md')).toBe('text')
    expect(kindOf('archive.tar.gz')).toBeNull()
    expect(kindOf('README')).toBeNull()
  })

  it('allows force transcription only for PDFs and images', () => {
    expect([canForce('a.pdf'), canForce('a.png'), canForce('a.md'), canForce('a.docx')]).toEqual([true, true, false, false])
  })
})
