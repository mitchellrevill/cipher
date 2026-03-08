// src/hooks/useJobStream.ts
import { useEffect } from 'react'
import { Job } from '../api/client'

export function useJobStream(jobId: string | null, onUpdate: (job: Job) => void) {
  useEffect(() => {
    if (!jobId) return
    const source = new EventSource(`/api/jobs/${jobId}/stream`)
    source.onmessage = (e) => {
      try {
        const job: Job = JSON.parse(e.data)
        onUpdate(job)
        if (job.status === 'complete' || job.status === 'failed') {
          source.close()
        }
      } catch {
        // ignore malformed SSE data
      }
    }
    source.onerror = () => source.close()
    return () => source.close()
  }, [jobId])  // intentionally omit onUpdate to avoid re-subscribing on every render
}
