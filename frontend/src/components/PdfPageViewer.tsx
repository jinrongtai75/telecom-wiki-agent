/**
 * PDF 뷰어 + 청크 bbox 오버레이
 *
 * preprocessing-master/frontend/src/components/PdfViewer.tsx 를 기반으로 통합:
 *  - pdfjs-dist 로 브라우저에서 직접 PDF 캔버스 렌더링 (서버 PNG 방식 제거)
 *  - 인증 헤더를 포함한 fetch → ArrayBuffer → pdfjsLib.getDocument({ data })
 *  - 드래그 영역 선택 (preprocessing-master 방식 그대로)
 *  - 청크 bbox 오버레이 (타입별 색상)
 *  - 오버레이 ref 기반 정확한 scroll-to-bbox (양방향 동기화)
 *  - IntersectionObserver 기반 lazy 캔버스 렌더링 (대용량 PDF 대응)
 */
import { useEffect, useRef, useState } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import type { ParsedChunkInfo } from '../types'

// Worker 설정 (preprocessing-master 방식 그대로)
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

// ── 타입 정의 ──────────────────────────────────────────────────────────────────
export interface RegionSelection {
  page: number
  pctX0: number   // 0.0–1.0 (페이지 너비 기준)
  pctY0: number   // 0.0–1.0 (페이지 높이 기준)
  pctX1: number
  pctY1: number
}

interface PageInfo {
  pageNum: number
  origWidth: number
  origHeight: number
}

// ── 타입별 오버레이 색상 (preprocessing-master OVERLAY_COLORS / BORDER_COLORS 채택) ──
const BORDER_COLORS: Record<string, string> = {
  text:    '#3b82f6',
  table:   '#f97316',
  image:   '#a855f7',
  summary: '#14b8a6',
  heading: '#eab308',
}

const OVERLAY_COLORS: Record<string, string> = {
  text:    'transparent',
  table:   'rgba(249,115,22,0.18)',
  image:   'rgba(168,85,247,0.18)',
  summary: 'rgba(20,184,166,0.18)',
  heading: 'rgba(234,179,8,0.12)',
}

function getChunkColorKey(chunk: ParsedChunkInfo): string {
  if (chunk.type === 'table')   return 'table'
  if (chunk.type === 'image')   return 'image'
  if (chunk.type === 'summary') return 'summary'
  if (chunk.is_heading)         return 'heading'
  return 'text'
}

function typeLabel(chunk: ParsedChunkInfo): string {
  if (chunk.type === 'table')   return 'TBL'
  if (chunk.type === 'image')   return 'IMG'
  if (chunk.type === 'summary') return 'SUM'
  if (chunk.is_heading)         return 'H'
  return ''
}

// ── 단일 페이지 컴포넌트 (preprocessing-master PdfPage + lazy 렌더링 + 드래그 선택) ──
function PdfPage({
  pdf, pageInfo, containerWidth,
  chunks, selectedChunkId,
  selectMode, onChunkSelect, onRegionSelect,
}: {
  pdf: PDFDocumentProxy
  pageInfo: PageInfo
  containerWidth: number
  chunks: ParsedChunkInfo[]
  selectedChunkId: string | null
  selectMode: boolean
  onChunkSelect: (chunk: ParsedChunkInfo) => void
  onRegionSelect: (region: RegionSelection) => void
}) {
  const canvasRef    = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [scale, setScale]           = useState(1)
  const [rendered, setRendered]     = useState(false)

  // 드래그 상태 (preprocessing-master PdfViewer.tsx 방식 그대로)
  const dragStart = useRef<{ x: number; y: number } | null>(null)
  const [dragRect, setDragRect] = useState<{ x: number; y: number; w: number; h: number } | null>(null)

  // 오버레이 ref 맵 (선택된 청크를 정확한 위치로 스크롤)
  const overlayRefs = useRef<Record<string, HTMLDivElement>>({})

  // ── Lazy 캔버스 렌더링 (IntersectionObserver) ─────────────────────────────
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setRendered(true) },
      { rootMargin: '600px', threshold: 0 },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  // ── 캔버스 렌더링 (preprocessing-master useEffect 방식 그대로) ────────────
  useEffect(() => {
    if (!rendered || containerWidth <= 0) return
    let cancelled = false
    ;(async () => {
      const page = await pdf.getPage(pageInfo.pageNum)
      const vp   = page.getViewport({ scale: 1 })
      const s    = containerWidth / vp.width
      const svp  = page.getViewport({ scale: s })

      const canvas = canvasRef.current
      if (!canvas || cancelled) return
      canvas.width  = svp.width
      canvas.height = svp.height
      setScale(s)
      await page.render({ canvas, viewport: svp }).promise
    })()
    return () => { cancelled = true }
  }, [pdf, pageInfo.pageNum, containerWidth, rendered])

  // ── 선택된 청크가 이 페이지에 있으면 해당 오버레이로 스크롤 ──────────────
  useEffect(() => {
    if (!selectedChunkId) return
    const el = overlayRefs.current[selectedChunkId]
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [selectedChunkId])

  // ── 드래그 핸들러 (preprocessing-master PdfViewer.tsx 로직 그대로) ─────────
  const getPos = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    return { x: e.clientX - rect.left, y: e.clientY - rect.top }
  }

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!selectMode) return
    e.preventDefault()
    dragStart.current = getPos(e)
    setDragRect(null)
  }

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!selectMode || !dragStart.current) return
    const cur = getPos(e)
    setDragRect({
      x: Math.min(dragStart.current.x, cur.x),
      y: Math.min(dragStart.current.y, cur.y),
      w: Math.abs(cur.x - dragStart.current.x),
      h: Math.abs(cur.y - dragStart.current.y),
    })
  }

  const handleMouseUp = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!selectMode || !dragStart.current) return
    const cur = getPos(e)
    const x0 = Math.min(dragStart.current.x, cur.x)
    const y0 = Math.min(dragStart.current.y, cur.y)
    const x1 = Math.max(dragStart.current.x, cur.x)
    const y1 = Math.max(dragStart.current.y, cur.y)
    dragStart.current = null
    setDragRect(null)

    if (x1 - x0 < 5 || y1 - y0 < 5) return // 너무 작은 선택 무시

    // CSS px → 퍼센트 좌표 변환
    // (preprocessing-master: CSS px → PDF 좌표계 변환; 여기서는 scale 적용)
    const W = e.currentTarget.offsetWidth
    const H = e.currentTarget.offsetHeight
    onRegionSelect({
      page: pageInfo.pageNum,
      pctX0: x0 / W,
      pctY0: y0 / H,
      pctX1: x1 / W,
      pctY1: y1 / H,
    })
  }

  const pageChunks = chunks.filter((c) => c.page === pageInfo.pageNum && c.bbox_json)
  const canvasW = rendered ? (pageInfo.origWidth * scale || '100%') : '100%'
  const aspectRatio = pageInfo.origHeight / pageInfo.origWidth

  return (
    <div style={{ marginBottom: 0 }} ref={containerRef}>
      <div
        style={{
          position: 'relative',
          width: canvasW,
          // 렌더 전 플레이스홀더 높이 (aspect ratio 유지)
          minHeight: rendered ? undefined : containerWidth * aspectRatio,
          background: '#fff',
          boxShadow: '0 2px 8px rgba(0,0,0,0.18)',
          borderRadius: 4,
          display: 'inline-block',
          cursor: selectMode ? 'crosshair' : 'default',
          userSelect: 'none',
          overflow: 'hidden',
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => { dragStart.current = null; setDragRect(null) }}
      >
        {/* 캔버스 (pdfjs-dist 렌더링) */}
        {rendered
          ? <canvas ref={canvasRef} style={{ display: 'block' }} />
          : <div style={{
              width: '100%',
              paddingBottom: `${aspectRatio * 100}%`,
              background: '#f5f5f5',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }} />
        }

        {/* 청크 bbox 오버레이 (preprocessing-master 스타일 채택) */}
        {rendered && pageChunks.map((chunk) => {
          try {
            const { x0, y0, x1, y1, pw, ph } = JSON.parse(chunk.bbox_json!) as {
              x0: number; y0: number; x1: number; y1: number; pw: number; ph: number
            }
            const isSelected = chunk.id === selectedChunkId
            const colorKey   = getChunkColorKey(chunk)
            const borderColor = BORDER_COLORS[colorKey]
            const bgColor     = isSelected
              ? (colorKey === 'text' ? 'rgba(59,130,246,0.25)' : OVERLAY_COLORS[colorKey].replace(/[\d.]+\)$/, '0.40)'))
              : OVERLAY_COLORS[colorKey]
            const label = typeLabel(chunk)

            return (
              <div
                key={chunk.id}
                ref={(el) => { if (el) overlayRefs.current[chunk.id] = el }}
                title={`[${chunk.type}] ${chunk.content?.slice(0, 60)}`}
                onClick={() => { if (!selectMode) onChunkSelect(chunk) }}
                style={{
                  position: 'absolute',
                  left:   `${(x0 / pw) * 100}%`,
                  top:    `${(y0 / ph) * 100}%`,
                  width:  `${((x1 - x0) / pw) * 100}%`,
                  height: `${((y1 - y0) / ph) * 100}%`,
                  backgroundColor: bgColor,
                  border: isSelected
                    ? `2px solid ${borderColor}`
                    : `1px solid ${borderColor}`,
                  outline:       isSelected ? `2px solid ${borderColor}` : 'none',
                  outlineOffset: isSelected ? '2px' : '0',
                  boxSizing:     'border-box',
                  cursor:        selectMode ? 'crosshair' : 'pointer',
                  zIndex:        isSelected ? 5 : 2,
                  pointerEvents: selectMode ? 'none' : 'auto',
                  transition:    'background-color 0.12s, border 0.12s',
                }}
              >
                {/* 타입 라벨 (preprocessing-master 방식 그대로) */}
                {label && (
                  <span style={{
                    position: 'absolute', top: 0, left: 0,
                    fontSize: 9, fontWeight: 700, lineHeight: '14px',
                    padding: '0 3px',
                    background: borderColor,
                    color: '#fff',
                    borderBottomRightRadius: 3,
                    pointerEvents: 'none',
                    userSelect: 'none',
                  }}>
                    {label}
                  </span>
                )}
              </div>
            )
          } catch {
            return null
          }
        })}

        {/* 드래그 선택 사각형 (preprocessing-master dragRect 스타일 그대로) */}
        {dragRect && (
          <div style={{
            position: 'absolute',
            left:   dragRect.x,
            top:    dragRect.y,
            width:  dragRect.w,
            height: dragRect.h,
            border: '2px dashed #f59e0b',
            background: 'rgba(245,158,11,0.15)',
            boxSizing: 'border-box',
            zIndex: 10,
            pointerEvents: 'none',
          }} />
        )}
      </div>
    </div>
  )
}

// ── 메인 컴포넌트 (preprocessing-master PdfViewer 메인 + 인증 fetch + ResizeObserver) ──
interface PdfPageViewerProps {
  docId: string
  totalPages: number           // 초기 placeholder용 (pdfjs 로드 후 실제 페이지 수 사용)
  chunks: ParsedChunkInfo[]
  selectedChunkId: string | null
  scrollToPage: number         // 0 = 스크롤 없음
  selectMode: boolean
  onChunkSelect: (chunk: ParsedChunkInfo) => void
  onRegionSelect: (region: RegionSelection) => void
}

export default function PdfPageViewer({
  docId,
  chunks,
  selectedChunkId,
  scrollToPage,
  selectMode,
  onChunkSelect,
  onRegionSelect,
}: PdfPageViewerProps) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const pageEls    = useRef<Record<number, HTMLDivElement>>({})

  const [pdf, setPdf]             = useState<PDFDocumentProxy | null>(null)
  const [pages, setPages]         = useState<PageInfo[]>([])
  const [containerWidth, setContainerWidth] = useState(0)
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState('')

  // ── ResizeObserver: 컨테이너 너비 추적 (preprocessing-master 방식 그대로) ──
  useEffect(() => {
    const el = wrapperRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      const w = entries[0].contentRect.width
      if (w > 0) setContainerWidth(w)
    })
    ro.observe(el)
    if (el.clientWidth > 0) setContainerWidth(el.clientWidth)
    return () => ro.disconnect()
  }, [])

  // ── PDF 로드 (인증 헤더 포함 fetch → ArrayBuffer → pdfjs) ──────────────────
  useEffect(() => {
    if (!docId) return
    let destroyed = false
    setLoading(true)
    setError('')
    setPdf(null)
    setPages([])
    pageEls.current = {}

    ;(async () => {
      try {
        const token = sessionStorage.getItem('access_token') ?? ''
        const res = await fetch(`/api/documents/${docId}/file`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const arrayBuffer = await res.arrayBuffer()
        if (destroyed) return

        const loaded = await pdfjsLib.getDocument({ data: arrayBuffer }).promise
        if (destroyed) { loaded.destroy(); return }

        // 전체 페이지 메타정보 수집 (origWidth/Height)
        const infos: PageInfo[] = []
        for (let i = 1; i <= loaded.numPages; i++) {
          const page = await loaded.getPage(i)
          const vp   = page.getViewport({ scale: 1 })
          infos.push({ pageNum: i, origWidth: vp.width, origHeight: vp.height })
        }
        if (destroyed) { loaded.destroy(); return }
        setPdf(loaded)
        setPages(infos)
      } catch (e) {
        if (!destroyed) setError(String(e))
      } finally {
        if (!destroyed) setLoading(false)
      }
    })()

    return () => { destroyed = true }
  }, [docId])

  // ── PAGE 구분자 클릭 시 스크롤 ────────────────────────────────────────────
  useEffect(() => {
    if (!scrollToPage) return
    const el = pageEls.current[scrollToPage]
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [scrollToPage])

  // ── 렌더링 ────────────────────────────────────────────────────────────────
  if (!docId) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
        문서를 선택해주세요
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
        PDF 불러오는 중...
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center text-red-400 text-sm px-4">
        PDF 렌더링 오류: {error}
      </div>
    )
  }

  return (
    <div ref={wrapperRef} className="flex-1 overflow-y-auto bg-gray-100 p-2">
      {/* selectMode 안내 배너 */}
      {selectMode && (
        <div className="sticky top-0 z-40 bg-amber-400 text-amber-900 text-xs font-semibold text-center py-1 rounded mb-2 shadow">
          드래그하여 영역 지정 — 겹치는 청크가 자동 선택됩니다
        </div>
      )}

      {/* 페이지 목록 */}
      {pdf && containerWidth > 0 && pages.map((pi) => (
        <div key={pi.pageNum} style={{ marginBottom: 20 }}>
          {/* 페이지 헤더 (preprocessing-master 스타일 채택) */}
          <div
            ref={(el) => { if (el) pageEls.current[pi.pageNum] = el }}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '4px 8px',
              marginBottom: 6,
              background: '#f5f5f5',
              borderRadius: 6,
              borderLeft: '3px solid #d9d9d9',
            }}
          >
            <span style={{ fontWeight: 700, fontSize: 11, color: '#595959', letterSpacing: '0.3px' }}>
              PAGE {pi.pageNum}
            </span>
            <span style={{ fontSize: 10, color: '#bfbfbf' }}>
              of {pages.length}
            </span>
          </div>

          <PdfPage
            pdf={pdf}
            pageInfo={pi}
            containerWidth={containerWidth}
            chunks={chunks}
            selectedChunkId={selectedChunkId}
            selectMode={selectMode}
            onChunkSelect={onChunkSelect}
            onRegionSelect={onRegionSelect}
          />
        </div>
      ))}
    </div>
  )
}
