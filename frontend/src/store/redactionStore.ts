import { create } from 'zustand'
import { Suggestion } from '../api/client'

interface RedactionStore {
  jobId: string | null
  suggestions: Suggestion[]
  activePage: number
  pageImages: string[]
  setJobId: (id: string) => void
  setSuggestions: (suggestions: Suggestion[]) => void
  toggleApproval: (id: string) => void
  setActivePage: (page: number) => void
  setPageImages: (images: string[]) => void
  addManualSuggestion: (suggestion: Suggestion) => void
}

export const useRedactionStore = create<RedactionStore>((set) => ({
  jobId: null,
  suggestions: [],
  activePage: 0,
  pageImages: [],
  setJobId: (jobId) => set({ jobId }),
  setSuggestions: (suggestions) => set({ suggestions }),
  toggleApproval: (id) => set((state) => ({
    suggestions: state.suggestions.map((s) =>
      s.id === id ? { ...s, approved: !s.approved } : s
    )
  })),
  setActivePage: (activePage) => set({ activePage }),
  setPageImages: (pageImages) => set({ pageImages }),
  addManualSuggestion: (suggestion) => set((state) => ({
    suggestions: [...state.suggestions, suggestion]
  }))
}))
