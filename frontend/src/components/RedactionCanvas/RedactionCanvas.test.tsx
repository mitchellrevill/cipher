import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'
import { RedactionCanvas } from './RedactionCanvas'
import { Suggestion } from '../../api/client'

vi.mock('fabric', () => ({
  Canvas: vi.fn(function () { return { add: vi.fn(), on: vi.fn(), dispose: vi.fn(), renderAll: vi.fn(), set: vi.fn() } }),
  Rect: vi.fn(function () { return {} }),
  Image: vi.fn(function () { return {} })
}))

const mockSuggestions: Suggestion[] = [{
  id: 's1', text: 'John', category: 'Person', reasoning: '', context: '', page_num: 0,
  rects: [{ x0: 10, y0: 10, x1: 100, y1: 30 }], approved: true, source: 'ai'
}]

describe('RedactionCanvas', () => {
  it('renders a canvas element', () => {
    const { container } = render(
      <RedactionCanvas
        backgroundImage={null}
        suggestions={mockSuggestions}
        pageNum={0}
        onManualRedaction={vi.fn()}
        scale={1}
      />
    )
    expect(container.querySelector('canvas')).toBeInTheDocument()
  })
})
