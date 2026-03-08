import { useEffect, useRef } from 'react'
import * as fabric from 'fabric'
import { Suggestion, Rect } from '../../api/client'

interface Props {
  backgroundImage: HTMLCanvasElement | null
  suggestions: Suggestion[]
  pageNum: number
  onManualRedaction: (rect: Rect) => void
  scale: number
}

export function RedactionCanvas({ backgroundImage, suggestions, pageNum, onManualRedaction, scale }: Props) {
  const canvasElRef = useRef<HTMLCanvasElement>(null)
  const fabricRef = useRef<fabric.Canvas | null>(null)

  useEffect(() => {
    if (!canvasElRef.current) return
    const width = backgroundImage?.width ?? 800
    const height = backgroundImage?.height ?? 1100

    fabricRef.current = new fabric.Canvas(canvasElRef.current, {
      width, height,
      isDrawingMode: false,
      selection: false,
    })

    if (backgroundImage) {
      const bg = new fabric.Image(backgroundImage as HTMLImageElement)
      fabricRef.current.set('backgroundImage', bg)
    }

    const pageSuggestions = suggestions.filter((s) => s.page_num === pageNum && s.approved)
    for (const s of pageSuggestions) {
      for (const r of s.rects) {
        const rect = new fabric.Rect({
          left: r.x0 * scale, top: r.y0 * scale,
          width: (r.x1 - r.x0) * scale, height: (r.y1 - r.y0) * scale,
          fill: 'rgba(255,255,0,0.4)', stroke: 'orange', strokeWidth: 1,
          selectable: false,
        })
        fabricRef.current.add(rect)
      }
    }

    fabricRef.current.renderAll()
    return () => { fabricRef.current?.dispose() }
  }, [backgroundImage, suggestions, pageNum, scale])

  return <canvas ref={canvasElRef} />
}
