import { useState } from 'react'
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { ParsedChunkInfo } from '../types'
import { api } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

interface Props {
  chunk: ParsedChunkInfo
  docId: string
  onUpdate: (updated: ParsedChunkInfo) => void
  onDelete: (id: string) => void
  onPageClick: (page: number) => void
  onSelect: (chunk: ParsedChunkInfo) => void
  isSelected?: boolean
}

export default function ChunkCard({ chunk, docId, onUpdate, onDelete, onPageClick, onSelect, isSelected }: Props) {
  const { provider, apiToken } = useAuth()
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState('')
  const [chatMsg, setChatMsg] = useState('')
  const [showChat, setShowChat] = useState(false)
  const [busy, setBusy] = useState(false)

  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: chunk.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  const effectiveContent = chunk.processed_content ?? chunk.content
  const isDiscarded = chunk.status === 'discarded'
  const isConfirmed = chunk.status === 'confirmed'

  const borderColor = isSelected
    ? 'border-blue-500'
    : isDiscarded
    ? 'border-gray-200'
    : isConfirmed
    ? 'border-green-400'
    : 'border-gray-200'

  if (isDiscarded) return null

  const handleSaveEdit = async () => {
    setBusy(true)
    try {
      const res = await api.updateChunk(docId, chunk.id, { content: editText })
      onUpdate(res.data)
    } finally {
      setBusy(false)
      setEditing(false)
    }
  }

  const handleToggleHeading = async () => {
    setBusy(true)
    try {
      const res = await api.updateChunk(docId, chunk.id, { is_heading: !chunk.is_heading })
      onUpdate(res.data)
    } finally {
      setBusy(false)
    }
  }

  const handleConfirm = async () => {
    setBusy(true)
    try {
      const res = await api.confirmChunk(docId, chunk.id)
      onUpdate(res.data)
    } finally {
      setBusy(false)
    }
  }

  const handleDelete = async () => {
    setBusy(true)
    try {
      await api.deleteChunk(docId, chunk.id)
      onDelete(chunk.id)
    } finally {
      setBusy(false)
    }
  }

  // TABLE actions
  const handleTableReview = async () => {
    if (!apiToken) return
    setBusy(true)
    try {
      const res = await api.tableReview(docId, chunk.id, provider, apiToken)
      onUpdate(res.data)
    } finally {
      setBusy(false)
    }
  }

  const handleTableFlatten = async () => {
    if (!apiToken) return
    setBusy(true)
    try {
      const res = await api.tableFlatten(docId, chunk.id, provider, apiToken)
      onUpdate(res.data)
    } finally {
      setBusy(false)
    }
  }

  const handleTableChat = async () => {
    if (!apiToken || !chatMsg.trim()) return
    setBusy(true)
    try {
      const res = await api.tableChat(docId, chunk.id, chatMsg, provider, apiToken)
      onUpdate(res.data)
      setChatMsg('')
      setShowChat(false)
    } finally {
      setBusy(false)
    }
  }

  // IMAGE actions
  const handleImageReview = async () => {
    if (!apiToken) return
    setBusy(true)
    try {
      const res = await api.imageReview(docId, chunk.id, provider, apiToken)
      onUpdate(res.data)
    } finally {
      setBusy(false)
    }
  }

  const handleImageChat = async () => {
    if (!apiToken || !chatMsg.trim()) return
    setBusy(true)
    try {
      const res = await api.imageChat(docId, chunk.id, chatMsg, provider, apiToken)
      onUpdate(res.data)
      setChatMsg('')
      setShowChat(false)
    } finally {
      setBusy(false)
    }
  }

  const typeBadge =
    chunk.type === 'table'
      ? 'bg-blue-100 text-blue-700'
      : chunk.type === 'image'
      ? 'bg-purple-100 text-purple-700'
      : chunk.type === 'summary'
      ? 'bg-amber-100 text-amber-700'
      : chunk.is_heading
      ? 'bg-yellow-100 text-yellow-700'
      : 'bg-gray-100 text-gray-500'

  const typeLabel =
    chunk.type === 'table'
      ? 'TABLE'
      : chunk.type === 'image'
      ? 'IMAGE'
      : chunk.type === 'summary'
      ? 'SUM'
      : chunk.is_heading
      ? 'HEAD'
      : 'TEXT'

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`bg-white rounded-lg border-2 ${borderColor} mb-2 overflow-hidden`}
    >
      {/* 카드 헤더 — 버튼 외 영역 클릭 시 청크 선택 (오른쪽→왼쪽 PDF 하이라이트) */}
      <div
        className="flex items-center gap-2 px-3 py-2 border-b border-gray-100 cursor-pointer hover:bg-gray-50"
        onClick={(e) => {
          // 버튼·드래그핸들 클릭은 무시
          if ((e.target as HTMLElement).closest('button, [data-drag-handle]')) return
          onSelect(chunk)
        }}
      >
        {/* 드래그 핸들 */}
        <div
          {...attributes}
          {...listeners}
          data-drag-handle
          className="cursor-grab text-gray-300 hover:text-gray-500 text-lg select-none"
          title="드래그로 순서 변경"
        >
          ⠿
        </div>

        <span className={`text-xs font-mono px-1.5 py-0.5 rounded font-medium ${typeBadge}`}>
          {typeLabel}
        </span>

        <button
          onClick={() => { onPageClick(chunk.page); onSelect(chunk) }}
          className="text-xs text-gray-400 hover:text-blue-500"
          title="PDF에서 위치 보기"
        >
          p.{chunk.page}
        </button>

        {chunk.section && (
          <span className="text-xs text-gray-400 truncate max-w-[120px]" title={chunk.section}>
            {chunk.section}
          </span>
        )}

        <div className="flex-1" />

        {/* 확인 버튼 */}
        {!isConfirmed && (
          <button
            onClick={handleConfirm}
            disabled={busy}
            className="text-xs text-green-600 hover:text-green-800 disabled:opacity-40"
            title="확인 완료"
          >
            ✓
          </button>
        )}

        {/* TEXT: heading 토글 */}
        {chunk.type === 'text' && (
          <button
            onClick={handleToggleHeading}
            disabled={busy}
            className={`text-xs px-1.5 py-0.5 rounded border disabled:opacity-40 ${
              chunk.is_heading
                ? 'border-yellow-400 text-yellow-700 bg-yellow-50'
                : 'border-gray-300 text-gray-500'
            }`}
            title="제목/본문 전환"
          >
            {chunk.is_heading ? 'H' : 'T'}
          </button>
        )}

        {/* 삭제 */}
        <button
          onClick={handleDelete}
          disabled={busy}
          className="text-xs text-red-400 hover:text-red-600 disabled:opacity-40"
          title="삭제"
        >
          ✕
        </button>
      </div>

      {/* 카드 본문 */}
      <div className="px-3 py-2">
        {/* TEXT 카드 */}
        {chunk.type === 'text' && (
          <>
            {editing ? (
              <div>
                <textarea
                  className="w-full border rounded text-sm p-2 min-h-[80px] focus:outline-none focus:ring-2 focus:ring-lgu-pink font-mono"
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                />
                <div className="flex gap-2 mt-1">
                  <button
                    onClick={handleSaveEdit}
                    disabled={busy}
                    className="text-xs bg-lgu-pink text-white px-3 py-1 rounded disabled:opacity-50"
                  >
                    저장
                  </button>
                  <button
                    onClick={() => setEditing(false)}
                    className="text-xs text-gray-500 px-2 py-1"
                  >
                    취소
                  </button>
                </div>
              </div>
            ) : (
              <p
                className={`text-sm text-gray-800 whitespace-pre-wrap cursor-pointer hover:bg-gray-50 rounded p-1 -ml-1 ${
                  chunk.is_heading ? 'font-semibold' : ''
                }`}
                onClick={() => {
                  setEditText(effectiveContent)
                  setEditing(true)
                }}
                title="클릭하여 편집"
              >
                {effectiveContent || <span className="text-gray-300 italic">내용 없음</span>}
              </p>
            )}
          </>
        )}

        {/* TABLE 카드 */}
        {chunk.type === 'table' && (
          <>
            <div className="flex gap-2 mb-2 flex-wrap">
              <button
                onClick={handleTableReview}
                disabled={busy || !apiToken}
                className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded hover:bg-blue-100 disabled:opacity-40"
              >
                VLM 검수
              </button>
              <button
                onClick={handleTableFlatten}
                disabled={busy || !apiToken}
                className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded hover:bg-blue-100 disabled:opacity-40"
              >
                평탄화
              </button>
              <button
                onClick={() => setShowChat(!showChat)}
                className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded hover:bg-gray-200"
              >
                채팅 편집
              </button>
            </div>

            {showChat && (
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  value={chatMsg}
                  onChange={(e) => setChatMsg(e.target.value)}
                  placeholder="편집 지시사항..."
                  className="flex-1 border rounded text-xs px-2 py-1 focus:outline-none focus:ring-1 focus:ring-lgu-pink"
                  onKeyDown={(e) => e.key === 'Enter' && handleTableChat()}
                />
                <button
                  onClick={handleTableChat}
                  disabled={busy || !chatMsg.trim()}
                  className="text-xs bg-lgu-pink text-white px-2 py-1 rounded disabled:opacity-50"
                >
                  전송
                </button>
              </div>
            )}

            <div className="overflow-x-auto">
              <pre className="text-xs font-mono text-gray-700 whitespace-pre">{effectiveContent}</pre>
            </div>
          </>
        )}

        {/* IMAGE 카드 */}
        {chunk.type === 'image' && (
          <>
            {chunk.image_b64 && (
              <img
                src={chunk.image_b64}
                alt="이미지 청크"
                className="max-w-full max-h-48 object-contain mb-2 rounded border"
              />
            )}
            {chunk.image_path && (
              <img
                src={chunk.image_path}
                alt="저장된 이미지"
                className="max-w-full max-h-48 object-contain mb-2 rounded border"
              />
            )}

            <div className="flex gap-2 mb-2 flex-wrap">
              <button
                onClick={handleImageReview}
                disabled={busy || !apiToken || !chunk.image_b64}
                className="text-xs bg-purple-50 text-purple-700 px-2 py-1 rounded hover:bg-purple-100 disabled:opacity-40"
              >
                VLM 검수
              </button>
              <button
                onClick={() => setShowChat(!showChat)}
                className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded hover:bg-gray-200"
              >
                채팅 편집
              </button>
            </div>

            {showChat && (
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  value={chatMsg}
                  onChange={(e) => setChatMsg(e.target.value)}
                  placeholder="편집 지시사항..."
                  className="flex-1 border rounded text-xs px-2 py-1 focus:outline-none focus:ring-1 focus:ring-lgu-pink"
                  onKeyDown={(e) => e.key === 'Enter' && handleImageChat()}
                />
                <button
                  onClick={handleImageChat}
                  disabled={busy || !chatMsg.trim()}
                  className="text-xs bg-lgu-pink text-white px-2 py-1 rounded disabled:opacity-50"
                >
                  전송
                </button>
              </div>
            )}

            {effectiveContent && (
              <p className="text-xs text-gray-600 bg-gray-50 rounded p-2 mt-1">{effectiveContent}</p>
            )}
          </>
        )}

        {/* SUMMARY 카드 */}
        {chunk.type === 'summary' && (
          <div className="border-l-4 border-amber-400 bg-amber-50 px-3 py-2 rounded-r text-sm text-amber-800 italic">
            {effectiveContent || <span className="text-amber-400">요약 없음</span>}
          </div>
        )}

        {busy && (
          <p className="text-xs text-gray-400 mt-1">처리 중...</p>
        )}
      </div>
    </div>
  )
}
