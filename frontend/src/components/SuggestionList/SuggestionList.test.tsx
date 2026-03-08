import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SuggestionList } from './SuggestionList'
import { Suggestion } from '../../api/client'

const suggestions: Suggestion[] = [
  { id: 's1', text: 'John Smith', category: 'Person', reasoning: 'PII', context: '', page_num: 0, rects: [], approved: true, source: 'ai' },
  { id: 's2', text: 'John Smith', category: 'Person', reasoning: 'PII', context: '', page_num: 1, rects: [], approved: true, source: 'ai' },
]

describe('SuggestionList', () => {
  it('groups suggestions by text', () => {
    render(<SuggestionList suggestions={suggestions} onToggle={vi.fn()} />)
    expect(screen.getAllByText(/John Smith/i).length).toBe(1)
  })

  it('calls onToggle when master checkbox clicked', () => {
    const onToggle = vi.fn()
    render(<SuggestionList suggestions={suggestions} onToggle={onToggle} />)
    const checkboxes = screen.getAllByRole('checkbox')
    fireEvent.click(checkboxes[0])
    expect(onToggle).toHaveBeenCalled()
  })
})
