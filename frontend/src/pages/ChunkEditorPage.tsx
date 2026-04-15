import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  arrayMove,
} from '@dnd-kit/sortable'
import { api } from '../services/api'
import { useAuth } from '../contexts/AuthContext'
import type { ParsedChunkInfo } from '../types'
import PdfPageViewer, { type RegionSelection } from '../components/PdfPageViewer'
import ChunkCard from '../components/ChunkCard'

export default function ChunkEditorPage() {
  const { docId } = useParams<{ docId: string }>()
  const navigate = useNavigate()
  const { provider, apiToken } = useAuth()

  const [chunks, setChunks] = useState<ParsedChunkInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [indexing, setIndexing] = useState(false)
  const [indexMsg, setIndexMsg] = useState('')
  const [scrollToPage, setScrollToPage] = useState(0)
  const [selectedChunk, setSelectedChunk] = useState<ParsedChunkInfo | null>(null)
  const [docName, setDocName] = useState('')
  const [reparsing, setReparsing] = useState(false)
  const [mdSaved, setMdSaved] = useState(false)
  const [selectMode, setSelectMode] = useState(false)   // PDF 드래그 영역 지정 모드

  // 청크 카드 DOM ref (오른쪽 패널 스크롤용)
  const chunkCardRefs = useRef<Record<string, HTMLDivElement>>({})

  const totalPages = chunks.length > 0 ? Math.max(...chunks.map((c) => c.page)) : 1

  const visibleChunks = chunks.filter((c) => c.status !== 'discarded')

  useEffect(() => {
    if (!docId) return
    api.getDocuments().then((r) => {
      const doc = r.data.find((d) => d.id === docId)
      if (doc) {
        setDocName(doc.original_name)
        if (doc.markdown_path) setMdSaved(true)
      }
    })
    api.getChunks(docId).then((r) => {
      setChunks(r.data)
    }).finally(() => setLoading(false))
  }, [docId])

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const handleDragEnd = useCallback(
    async (event: DragEndEvent) => {
      const { active, over } = event
      if (!over || active.id === over.id) return

      const oldIndex = visibleChunks.findIndex((c) => c.id === active.id)
      const newIndex = visibleChunks.findIndex((c) => c.id === over.id)
      const reordered = arrayMove(visibleChunks, oldIndex, newIndex)

      // 전체 chunks 배열에서 순서 업데이트 (discarded 제외 후 재조합)
      const discarded = chunks.filter((c) => c.status === 'discarded')
      const newFull = [...reordered, ...discarded]
      setChunks(newFull)

      if (docId) {
        await api.reorderChunks(docId, reordered.map((c) => c.id))
      }
    },
    [chunks, visibleChunks, docId],
  )

  const handleChunkUpdate = (updated: ParsedChunkInfo) => {
    setChunks((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
  }

  const handleChunkDelete = (id: string) => {
    setChunks((prev) => prev.map((c) => c.id === id ? { ...c, status: 'discarded' as const } : c))
  }

  const handlePageClick = (page: number) => {
    setScrollToPage(page)
    setSelectedChunk(null)
  }

  const handleSelectChunk = (chunk: ParsedChunkInfo) => {
    setSelectedChunk(chunk)
    setScrollToPage(0)   // PdfPageViewer가 overlayRef 기반으로 정확한 위치로 스크롤
    // 오른쪽 패널 해당 청크 카드로 스크롤
    chunkCardRefs.current[chunk.id]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }

  /**
   * PDF 드래그 영역 선택 → 겹치는 청크 중 overlap이 가장 큰 청크를 선택
   * preprocessing-master Viewer.tsx 의 addManualObject 패턴을 참고하여
   * 영역 좌표(퍼센트)와 청크 bbox(퍼센트)의 교집합 넓이로 최적 청크를 찾음
   */
  const handleRegionSelect = useCallback((region: RegionSelection) => {
    const pageChunks = visibleChunks.filter((c) => c.page === region.page && c.bbox_json)
    let bestChunk: ParsedChunkInfo | null = null
    let bestOverlap = 0

    for (const chunk of pageChunks) {
      try {
        const { x0, y0, x1, y1, pw, ph } = JSON.parse(chunk.bbox_json!) as {
          x0: number; y0: number; x1: number; y1: number; pw: number; ph: number
        }
        // 청크 bbox → 퍼센트 좌표
        const cPx0 = x0 / pw, cPy0 = y0 / ph
        const cPx1 = x1 / pw, cPy1 = y1 / ph

        // 교집합
        const ix0 = Math.max(region.pctX0, cPx0)
        const iy0 = Math.max(region.pctY0, cPy0)
        const ix1 = Math.min(region.pctX1, cPx1)
        const iy1 = Math.min(region.pctY1, cPy1)
        if (ix1 <= ix0 || iy1 <= iy0) continue

        const overlap = (ix1 - ix0) * (iy1 - iy0)
        if (overlap > bestOverlap) {
          bestOverlap = overlap
          bestChunk = chunk
        }
      } catch { /* bbox 파싱 오류 무시 */ }
    }

    if (bestChunk) {
      handleSelectChunk(bestChunk)
    }
    // 영역 지정 후 모드 유지 (사용자가 직접 토글로 해제)
  }, [visibleChunks]) // eslint-disable-line react-hooks/exhaustive-deps


  const handleReparse = async () => {
    if (!docId || reparsing) return
    if (!confirm('기존 편집 내용이 초기화됩니다. 재파싱하시겠습니까?')) return
    setReparsing(true)
    setIndexMsg('')
    try {
      await api.reparseDocument(docId)
      const r = await api.getChunks(docId)
      setChunks(r.data)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setIndexMsg(`❌ ${msg ?? '재파싱 실패'}`)
    } finally {
      setReparsing(false)
    }
  }

  const handleIndex = async () => {
    if (!docId || !apiToken) {
      setIndexMsg('❌ API 토큰이 없습니다. 토큰 페이지에서 설정해주세요.')
      return
    }
    setIndexing(true)
    setIndexMsg('요약 생성 중...')
    try {
      // 1. 요약 자동 생성 (실패해도 계속 진행)
      try {
        await api.summarizeDocument(docId, provider, apiToken)
        const r = await api.getChunks(docId)
        setChunks(r.data)
      } catch (sumErr: unknown) {
        const detail = (sumErr as { response?: { data?: { detail?: string } }; code?: string })
        const isTimeout = detail?.code === 'ECONNABORTED'
        const errMsg = detail?.response?.data?.detail
        setIndexMsg(`⚠️ 요약 생성 ${isTimeout ? '타임아웃' : (errMsg ?? '실패')} — DB 저장 계속 진행 중...`)
      }

      // 2. MD 저장 + ChromaDB 인덱싱
      setIndexMsg((prev) => prev.startsWith('⚠️') ? prev.replace('계속 진행 중...', '→ DB 저장 중...') : 'DB 저장 중...')
      await api.indexDocument(docId, provider, apiToken)
      setMdSaved(true)
      setIndexMsg('✅ DB 저장 완료!')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setIndexMsg(`❌ ${msg ?? 'DB 저장 실패'}`)
    } finally {
      setIndexing(false)
    }
  }

  const pendingCount = visibleChunks.filter((c) => c.status === 'pending').length
  const confirmedCount = visibleChunks.filter((c) => c.status === 'confirmed').length
  const discardedCount = chunks.filter((c) => c.status === 'discarded').length

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-400">
        청크 로딩 중...
      </div>
    )
  }

  return (
    <div className="h-screen bg-gray-50 flex flex-col overflow-hidden">
      {/* 헤더 */}
      <header className="bg-lgu-dark text-white px-4 py-3 flex items-center gap-3 flex-shrink-0">
        <button
          onClick={() => navigate('/admin')}
          className="text-xs bg-white/10 px-2 py-1 rounded hover:bg-white/20"
        >
          ← 관리자
        </button>
        <h1 className="font-bold text-sm flex-1 truncate">{docName || docId}</h1>
        <div className="text-xs text-white/60 hidden sm:block">
          전체 {visibleChunks.length} · 확인 {confirmedCount} · 미확인 {pendingCount} · 제외 {discardedCount}
        </div>
        {mdSaved && (
          <span className="text-xs bg-green-500/20 text-green-200 border border-green-400/30 px-2 py-0.5 rounded">
            DB 저장됨
          </span>
        )}
        {/* 영역 지정 토글 (preprocessing-master Toolbar.tsx selectMode 버튼 방식 채택) */}
        <button
          onClick={() => setSelectMode((v) => !v)}
          className={`text-xs px-3 py-1.5 rounded font-medium transition-colors ${
            selectMode
              ? 'bg-amber-400 text-amber-900 hover:bg-amber-300'
              : 'bg-white/10 text-white hover:bg-white/20'
          }`}
          title="PDF에서 마우스로 영역을 드래그하여 청크를 선택합니다"
        >
          {selectMode ? '✕ 영역지정 취소' : '⊹ 영역지정'}
        </button>
        <button
          onClick={handleReparse}
          disabled={reparsing || indexing}
          className="text-xs bg-white/10 text-white px-3 py-1.5 rounded hover:bg-white/20 disabled:opacity-50"
        >
          {reparsing ? '재파싱 중...' : '재파싱'}
        </button>
        <button
          onClick={handleIndex}
          disabled={indexing || reparsing || !apiToken}
          className="text-xs bg-lgu-pink text-white px-3 py-1.5 rounded hover:opacity-90 disabled:opacity-50 font-medium"
          title={!apiToken ? 'API 토큰 필요' : '요약 생성 후 DB에 저장'}
        >
          {indexing ? '저장 중...' : 'DB저장'}
        </button>
      </header>

      {indexMsg && (
        <div className="px-4 py-2 bg-white border-b text-sm text-gray-600">{indexMsg}</div>
      )}

      {/* 본문: 분할 뷰 */}
      <div className="flex flex-1 overflow-hidden">
        {/* 왼쪽: PDF 뷰어 (40%) */}
        <div className="w-2/5 border-r flex flex-col overflow-hidden">
          <PdfPageViewer
            docId={docId ?? ''}
            totalPages={totalPages}
            chunks={visibleChunks}
            selectedChunkId={selectedChunk?.id ?? null}
            scrollToPage={scrollToPage}
            selectMode={selectMode}
            onChunkSelect={handleSelectChunk}
            onRegionSelect={handleRegionSelect}
          />
          {/* totalPages는 pdfjs가 내부적으로 계산하나, ChunkEditorPage에선 여전히 PAGE 구분 등에서 사용 */}
        </div>

        {/* 오른쪽: 청크 목록 (60%) */}
        <div className="w-3/5 overflow-y-auto p-3">
          {visibleChunks.length === 0 ? (
            <div className="text-center py-16">
              <p className="text-gray-500 text-sm mb-4">
                {reparsing ? '재파싱 중...' : 'PDF 청크가 없습니다. 재파싱을 실행하세요.'}
              </p>
              {!reparsing && (
                <button
                  onClick={handleReparse}
                  className="bg-lgu-pink text-white px-4 py-2 rounded-lg text-sm font-medium hover:opacity-90"
                >
                  PDF 재파싱 시작
                </button>
              )}
            </div>
          ) : (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={visibleChunks.map((c) => c.id)}
                strategy={verticalListSortingStrategy}
              >
                {/* 페이지별 구분선과 청크 카드 */}
                {(() => {
                  const elements: React.ReactNode[] = []
                  let lastPage = -1
                  visibleChunks.forEach((chunk) => {
                    if (chunk.page !== lastPage) {
                      elements.push(
                        <div key={`page-sep-${chunk.page}`} className="flex items-center gap-2 my-3">
                          <div className="flex-1 h-px bg-gray-200" />
                          <button
                            onClick={() => handlePageClick(chunk.page)}
                            className="text-xs text-gray-400 hover:text-lgu-pink px-2 py-0.5 rounded bg-gray-100 hover:bg-pink-50"
                          >
                            PAGE {chunk.page}
                          </button>
                          <div className="flex-1 h-px bg-gray-200" />
                        </div>,
                      )
                      lastPage = chunk.page
                    }
                    elements.push(
                      <div
                        key={chunk.id}
                        ref={(el) => { if (el) chunkCardRefs.current[chunk.id] = el }}
                      >
                        <ChunkCard
                          chunk={chunk}
                          docId={docId ?? ''}
                          onUpdate={handleChunkUpdate}
                          onDelete={handleChunkDelete}
                          onPageClick={handlePageClick}
                          onSelect={handleSelectChunk}
                          isSelected={selectedChunk?.id === chunk.id}
                        />
                      </div>,
                    )
                  })
                  return elements
                })()}
              </SortableContext>
            </DndContext>
          )}
        </div>
      </div>
    </div>
  )
}
