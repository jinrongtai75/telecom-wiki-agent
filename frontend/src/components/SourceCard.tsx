import { useState, useEffect } from 'react'
import type { SourceInfo } from '../types'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

function useAuthImage(url: string | null, enabled: boolean) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!enabled || !url) return
    setBlobUrl(null)
    setError(false)

    const token = sessionStorage.getItem('access_token') ?? ''
    fetch(`${API_BASE}${url}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.blob()
      })
      .then((blob) => setBlobUrl(URL.createObjectURL(blob)))
      .catch(() => setError(true))

    return () => {
      setBlobUrl((prev) => { if (prev) URL.revokeObjectURL(prev); return null })
    }
  }, [url, enabled])

  return { blobUrl, error }
}

export default function SourceCard({ source, dark = false }: { source: SourceInfo; dark?: boolean }) {
  const [previewOpen, setPreviewOpen] = useState(false)

  const pagePreviewUrl =
    !source.from_3gpp && source.doc_id && source.page > 0
      ? `/api/documents/${source.doc_id}/page/${source.page}`
      : null

  const externalUrl = source.from_3gpp && source.section ? source.section : null
  const isClickable = !!(pagePreviewUrl || externalUrl)

  // 모달이 열릴 때만 이미지 fetch (인증 헤더 포함)
  const { blobUrl, error } = useAuthImage(pagePreviewUrl, previewOpen)

  const handleClick = () => {
    if (externalUrl) {
      window.open(externalUrl, '_blank', 'noopener,noreferrer')
    } else if (pagePreviewUrl) {
      setPreviewOpen(true)
    }
  }

  const cardClass = dark
    ? `flex items-start gap-3 p-3 bg-white/5 rounded-lg border border-white/10 transition-colors ${isClickable ? 'cursor-pointer hover:bg-white/10 hover:border-white/20' : ''}`
    : `flex items-start gap-3 p-3 bg-gray-50 rounded-lg border border-gray-100 transition-colors ${isClickable ? 'cursor-pointer hover:bg-gray-100' : ''}`

  return (
    <>
      <div
        className={cardClass}
        onClick={isClickable ? handleClick : undefined}
        title={externalUrl ? '클릭하여 3GPP 규격 열기' : pagePreviewUrl ? '클릭하여 페이지 미리보기' : undefined}
      >
        {/* 썸네일: 저장된 이미지만 표시 (페이지 썸네일은 인증 문제로 제거) */}
        {source.image_path && (
          <img
            src={source.image_path}
            alt="출처 이미지"
            className="w-16 h-16 object-cover rounded flex-shrink-0 border"
          />
        )}

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            {source.from_3gpp && (
              <span className={`text-xs px-1.5 py-0.5 rounded ${dark ? 'bg-blue-500/20 text-blue-400' : 'bg-blue-100 text-blue-700'}`}>3GPP</span>
            )}
            <span className={`text-xs font-medium truncate ${dark ? 'text-gray-300' : 'text-gray-700'}`}>{source.filename}</span>
          </div>
          {source.page > 0 && (
            <p className={`text-xs mt-0.5 ${dark ? 'text-gray-500' : 'text-gray-500'}`}>p.{source.page}</p>
          )}
          {source.section && (
            <p className={`text-xs mt-0.5 truncate ${dark ? 'text-gray-600' : 'text-gray-400'}`}>{source.section}</p>
          )}
          <div className="mt-1 flex items-center gap-2">
            <span className={`text-xs ${dark ? 'text-gray-600' : 'text-gray-400'}`}>관련도 {Math.round(source.score * 100)}%</span>
            {externalUrl && <span className="text-xs text-[#E6007E]">규격 열기 →</span>}
            {pagePreviewUrl && <span className="text-xs text-[#E6007E]">미리보기 →</span>}
          </div>
        </div>
      </div>

      {/* 페이지 미리보기 모달 */}
      {previewOpen && pagePreviewUrl && (
        <div
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
          onClick={() => setPreviewOpen(false)}
        >
          <div
            className="bg-[#1e1e35] border border-white/10 rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-3 border-b border-white/10">
              <div>
                <p className="text-sm font-medium text-gray-200 truncate">{source.filename}</p>
                <p className="text-xs text-gray-500">p.{source.page} · 관련도 {Math.round(source.score * 100)}%</p>
              </div>
              <button
                onClick={() => setPreviewOpen(false)}
                className="text-gray-500 hover:text-gray-300 text-xl leading-none px-2"
              >
                ×
              </button>
            </div>
            <div className="p-3 flex items-center justify-center min-h-40">
              {!blobUrl && !error && (
                <div className="flex gap-1.5">
                  <span className="w-2 h-2 bg-[#E6007E]/60 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 bg-[#E6007E]/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 bg-[#E6007E]/60 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              )}
              {error && (
                <p className="text-sm text-gray-500">페이지 이미지를 불러올 수 없습니다</p>
              )}
              {blobUrl && (
                <img
                  src={blobUrl}
                  alt={`${source.filename} p.${source.page}`}
                  className="w-full rounded"
                />
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
