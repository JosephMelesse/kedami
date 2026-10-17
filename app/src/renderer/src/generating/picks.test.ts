import { describe, expect, it } from 'vitest'
import { bareNumber, numberAndTitle, pieces, problemList } from './picks'

describe('picker text', () => {
  it('splits pasted text at commas and line breaks', () => {
    expect(pieces('1, 15,\n206\n\n two sum ,')).toEqual(['1', '15', '206', 'two sum'])
    expect(pieces(' , \n')).toEqual([])
  })

  it.each([
    ['146', 146],
    ['#146', 146],
    ['146.', 146],
    ['LeetCode 146', 146],
    ['146 LRU Cache', null],
    ['two sum', null],
    ['3sum', null]
  ])('reads %j as the bare number %j', (piece, number) => {
    expect(bareNumber(piece)).toBe(number)
  })

  it.each([
    ['146 LRU Cache', { number: 146, title: 'LRU Cache' }],
    ['146. LRU Cache', { number: 146, title: 'LRU Cache' }],
    ['#146 - LRU Cache', { number: 146, title: 'LRU Cache' }],
    ['50) Pow(x, n)', { number: 50, title: 'Pow(x, n)' }],
    ['146', null],
    ['146 ???', null],
    ['3sum', null],
    ['LRU Cache', null]
  ])('reads %j as a number and title', (piece, expected) => {
    expect(numberAndTitle(piece)).toEqual(expected)
  })

  it('writes the picks as the problem list the pipeline reads, in picked order', () => {
    expect(
      problemList([
        { number: 15, title: '3sum', difficulty: 'Medium' },
        { number: 146, title: 'LRU Cache', difficulty: null }
      ])
    ).toBe('15. 3sum\n146. LRU Cache\n')
  })
})
