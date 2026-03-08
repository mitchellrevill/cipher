import axios from 'axios'

export const api = axios.create({ baseURL: '/api' })

export const uploadDocument = (file: File, instructions: string) => {
  const form = new FormData()
  form.append('file', file)
  form.append('instructions', instructions)
  return api.post<{ job_id: string }>('/jobs', form)
}

export const getJob = (jobId: string) =>
  api.get<Job>(`/jobs/${jobId}`)

export const toggleApproval = (jobId: string, suggestionId: string, approved: boolean) =>
  api.patch(`/jobs/${jobId}/redactions/${suggestionId}`, { approved })

export const applyRedactions = (jobId: string) =>
  api.post(`/jobs/${jobId}/redactions/apply`)

export const chat = (req: ChatRequest) =>
  api.post<ChatResponse>('/agent/chat', req)

export interface Job {
  job_id: string
  status: 'pending' | 'processing' | 'complete' | 'failed'
  suggestions: Suggestion[]
  page_count?: number
}

export interface Suggestion {
  id: string
  text: string
  category: string
  reasoning: string
  context: string
  page_num: number
  rects: Rect[]
  approved: boolean
  source: string
}

export interface Rect { x0: number; y0: number; x1: number; y1: number }

export interface ChatRequest {
  job_id: string
  message: string
  previous_response_id?: string
}

export interface ChatResponse {
  text: string
  response_id: string
  tool_calls: unknown[]
}
