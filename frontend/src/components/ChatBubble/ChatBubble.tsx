import { useState, useRef, FormEvent } from 'react'
import { chat } from '../../api/client'

interface Message { role: 'user' | 'assistant'; text: string }

interface Props {
  jobId: string
  onRedactionChange: () => void
}

export function ChatBubble({ jobId, onRedactionChange }: Props) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const previousResponseId = useRef<string | undefined>()

  const send = async (e: FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return
    const userMessage = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', text: userMessage }])
    setLoading(true)

    try {
      const { data } = await chat({
        job_id: jobId,
        message: userMessage,
        previous_response_id: previousResponseId.current
      })
      previousResponseId.current = data.response_id
      setMessages((prev) => [...prev, { role: 'assistant', text: data.text }])
      if (data.tool_calls?.length > 0) {
        onRedactionChange()
      }
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', text: 'Sorry, something went wrong.' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <button aria-label="Open chat" onClick={() => setOpen((o) => !o)} className="chat-toggle">
        Chat
      </button>
      {open && (
        <div className="chat-bubble">
          <div className="chat-messages">
            {messages.map((m, i) => (
              <div key={i} className={`chat-message ${m.role}`}>{m.text}</div>
            ))}
            {loading && <div className="chat-message assistant">Thinking…</div>}
          </div>
          <form onSubmit={send} className="chat-input-form">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about redactions..."
              disabled={loading}
            />
            <button type="submit" disabled={loading}>Send</button>
          </form>
        </div>
      )}
    </>
  )
}
