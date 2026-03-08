import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PDFViewer } from './PDFViewer'

vi.mock('pdfjs-dist', () => ({
  getDocument: vi.fn(() => ({
    promise: Promise.resolve({
      numPages: 2,
      getPage: vi.fn(() => Promise.resolve({
        getViewport: vi.fn(() => ({ width: 595, height: 842, scale: 1 })),
        render: vi.fn(() => ({ promise: Promise.resolve() }))
      }))
    })
  })),
  GlobalWorkerOptions: { workerSrc: '' }
}))

describe('PDFViewer', () => {
  it('renders page navigation controls', () => {
    render(<PDFViewer pdfUrl="/test.pdf" onPageRendered={vi.fn()} />)
    expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument()
  })
})
