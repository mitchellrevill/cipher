import { useEffect, useRef, useState } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import { useRedactionStore } from '../../store/redactionStore'

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url
).toString()

interface Props {
  pdfUrl: string
  onPageRendered: (canvas: HTMLCanvasElement, pageNum: number) => void
}

export function PDFViewer({ pdfUrl, onPageRendered }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const { activePage, setActivePage } = useRedactionStore()
  const [totalPages, setTotalPages] = useState(0)
  const pdfRef = useRef<pdfjsLib.PDFDocumentProxy | null>(null)

  useEffect(() => {
    pdfjsLib.getDocument(pdfUrl).promise.then((pdf) => {
      pdfRef.current = pdf
      setTotalPages(pdf.numPages)
    })
  }, [pdfUrl])

  useEffect(() => {
    if (!pdfRef.current || !canvasRef.current) return
    pdfRef.current.getPage(activePage + 1).then((page) => {
      const viewport = page.getViewport({ scale: 1.5 })
      const canvas = canvasRef.current!
      canvas.width = viewport.width
      canvas.height = viewport.height
      page.render({ canvasContext: canvas.getContext('2d')!, viewport })
        .promise.then(() => onPageRendered(canvas, activePage))
    })
  }, [activePage, onPageRendered])

  return (
    <div className="pdf-viewer">
      <div className="nav-controls">
        <button
          aria-label="Previous page"
          disabled={activePage === 0}
          onClick={() => setActivePage(activePage - 1)}
        >Previous</button>
        <span>Page {activePage + 1} of {totalPages}</span>
        <button
          aria-label="Next page"
          disabled={activePage >= totalPages - 1}
          onClick={() => setActivePage(activePage + 1)}
        >Next</button>
      </div>
      <canvas ref={canvasRef} />
    </div>
  )
}
