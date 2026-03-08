// src/App.tsx
import { useState, useCallback } from 'react'
import { uploadDocument, toggleApproval, applyRedactions, getJob } from './api/client'
import { useRedactionStore } from './store/redactionStore'
import { useJobStream } from './hooks/useJobStream'
import { PDFViewer } from './components/PDFViewer/PDFViewer'
import { RedactionCanvas } from './components/RedactionCanvas/RedactionCanvas'
import { SuggestionList } from './components/SuggestionList/SuggestionList'
import { ChatBubble } from './components/ChatBubble/ChatBubble'

export default function App() {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [backgroundCanvas, setBackgroundCanvas] = useState<HTMLCanvasElement | null>(null)
  const [uploading, setUploading] = useState(false)
  const [status, setStatus] = useState<string>('')

  const {
    jobId, suggestions, activePage,
    setJobId, setSuggestions, toggleApproval: storeToggle
  } = useRedactionStore()

  useJobStream(jobId, (job) => {
    setStatus(job.status)
    if (job.suggestions?.length) setSuggestions(job.suggestions)
  })

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      setPdfUrl(URL.createObjectURL(file))
      const { data } = await uploadDocument(file, '')
      setJobId(data.job_id)
      setStatus('pending')
    } finally {
      setUploading(false)
    }
  }

  const handleToggle = async (ids: string[], approved: boolean) => {
    ids.forEach((id) => storeToggle(id))
    if (jobId) await Promise.all(ids.map((id) => toggleApproval(jobId, id, approved)))
  }

  const handleApply = async () => {
    if (!jobId) return
    await applyRedactions(jobId)
    window.open(`/api/jobs/${jobId}/download`, '_blank')
  }

  const refreshSuggestions = useCallback(async () => {
    if (!jobId) return
    const { data } = await getJob(jobId)
    setSuggestions(data.suggestions)
  }, [jobId, setSuggestions])

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', height: '100vh', overflow: 'hidden' }}>
      <aside style={{ borderRight: '1px solid #ccc', padding: '1rem', overflowY: 'auto' }}>
        <h2>AI Redactor</h2>
        <input type="file" accept=".pdf" onChange={handleUpload} disabled={uploading} />
        {status && <p>Status: {status}</p>}
        <SuggestionList suggestions={suggestions} onToggle={handleToggle} />
        <button onClick={handleApply} disabled={!jobId || status !== 'complete'}>
          Generate Redacted PDF
        </button>
      </aside>
      <main style={{ position: 'relative', overflow: 'auto' }}>
        {pdfUrl && (
          <>
            <PDFViewer pdfUrl={pdfUrl} onPageRendered={(canvas) => setBackgroundCanvas(canvas)} />
            <RedactionCanvas
              backgroundImage={backgroundCanvas}
              suggestions={suggestions}
              pageNum={activePage}
              onManualRedaction={() => {}}
              scale={1}
            />
          </>
        )}
        {jobId && <ChatBubble jobId={jobId} onRedactionChange={refreshSuggestions} />}
      </main>
    </div>
  )
}
