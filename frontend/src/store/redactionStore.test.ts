import { describe, it, expect, beforeEach } from 'vitest'
import { useRedactionStore } from './redactionStore'
import { act, renderHook } from '@testing-library/react'

describe('redactionStore', () => {
  beforeEach(() => {
    useRedactionStore.setState({ suggestions: [], activePage: 0, jobId: null, pageImages: [] })
  })

  it('toggles suggestion approval', () => {
    const { result } = renderHook(() => useRedactionStore())
    act(() => {
      result.current.setSuggestions([
        { id: 's1', text: 'John', category: 'Person', reasoning: '', context: '', page_num: 0, rects: [], approved: true, source: 'ai' }
      ])
    })
    act(() => result.current.toggleApproval('s1'))
    expect(result.current.suggestions[0].approved).toBe(false)
  })

  it('sets active page', () => {
    const { result } = renderHook(() => useRedactionStore())
    act(() => result.current.setActivePage(3))
    expect(result.current.activePage).toBe(3)
  })
})
