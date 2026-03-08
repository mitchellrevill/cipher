import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ChatBubble } from './ChatBubble'

vi.mock('../../api/client', () => ({
  chat: vi.fn().mockResolvedValue({
    data: { text: 'I found 3 redactions.', response_id: 'resp-1', tool_calls: [] }
  })
}))

describe('ChatBubble', () => {
  it('sends message and displays response', async () => {
    render(<ChatBubble jobId="job-1" onRedactionChange={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /open chat/i }))
    const input = screen.getByPlaceholderText(/ask about redactions/i)
    fireEvent.change(input, { target: { value: 'What was redacted?' } })
    fireEvent.submit(input.closest('form')!)
    await waitFor(() => screen.getByText('I found 3 redactions.'))
    const { chat } = await import('../../api/client')
    expect(chat).toHaveBeenCalledWith(expect.objectContaining({ message: 'What was redacted?' }))
  })
})
