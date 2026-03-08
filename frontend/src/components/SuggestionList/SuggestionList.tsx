import { useState } from 'react'
import { Suggestion } from '../../api/client'

interface Props {
  suggestions: Suggestion[]
  onToggle: (ids: string[], approved: boolean) => void
}

export function SuggestionList({ suggestions, onToggle }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const groups = suggestions.reduce<Record<string, Suggestion[]>>((acc, s) => {
    acc[s.text] = acc[s.text] ?? []
    acc[s.text].push(s)
    return acc
  }, {})

  return (
    <div className="suggestion-list">
      {Object.entries(groups).map(([text, instances]) => {
        const allApproved = instances.every((s) => s.approved)
        const ids = instances.map((s) => s.id)
        const isExpanded = expanded.has(text)

        return (
          <div key={text} className="suggestion-group">
            <div className="suggestion-group-header">
              <input
                type="checkbox"
                checked={allApproved}
                onChange={(e) => onToggle(ids, e.target.checked)}
              />
              <span><strong>{text}</strong> ({instances[0].category}) — {instances.length} instance(s)</span>
              <button onClick={() => setExpanded((prev) => {
                const next = new Set(prev)
                isExpanded ? next.delete(text) : next.add(text)
                return next
              })}>
                {isExpanded ? '▲' : '▼'}
              </button>
            </div>

            {isExpanded && instances.map((s) => (
              <div key={s.id} className="suggestion-instance">
                <input
                  type="checkbox"
                  checked={s.approved}
                  onChange={(e) => onToggle([s.id], e.target.checked)}
                />
                <span>Pg {s.page_num + 1} — {s.reasoning}</span>
              </div>
            ))}
          </div>
        )
      })}
    </div>
  )
}
