import { useState } from 'react'
import type { SourceInfo } from '../types'

export default function SourceCard({ source, dark = false }: { source: SourceInfo; dark?: boolean }) {
  const [previewOpen, setPreviewOpen] = useState(false)

  // PDF 페이지 미리보기 URL (doc_id + page_num)
  const pagePreviewUrl =
    !source.from_3gpp && source.doc_id && source.page > 0
      ? `/api/documents/${source.doc_id}/page/${source.page}`
      : null

  const cardClass = dark
    ? 'flex items-start gap-3 p-3 bg-white/5 rounded-lg border border-white/10 cursor-pointer hover:bg-white/10 hover:border-white/20 transition-colors'
    : 'flex items-start gap-3 p-3 bg-gray-50 rounded-lg border border-gray-100 cursor-pointer hover:bg-gray-100 transition-colors'

  return (
    <>
      <div
        className={cardClass}
        onClick={() => pagePreviewUrl && setPreviewOpen(true)}
        title={pagePreviewUrl ? '클릭하여 페이지 미리보기' : undefined}
      >
        {/* 저장된 이미지 또는 페이지 썸네일 */}
        {source.image_path ? (
          <img
            src={source.image_path}
            alt="출처 이미지"
            className="w-16 h-16 object-cover rounded flex-shrink-0 border"
          />
        ) : pagePreviewUrl ? (
          <img
            src={pagePreviewUrl}
            alt={`p.${source.page}`}
            className="w-16 h-16 object-cover rounded flex-shrink-0 border bg-white"
            loading="lazy"
          />
        ) : null}

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
            {pagePreviewUrl && (
              <span className="text-xs text-[#E6007E]">미리보기 →</span>
            )}
          </div>
        </div>
      </div>

      {/* 페이지 미리보기 모달 */}
      {previewOpen && pagePreviewUrl && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
          onClick={() => setPreviewOpen(false)}
        >
          <div
            className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-3 border-b">
              <div>
                <p className="text-sm font-medium text-gray-800 truncate">{source.filename}</p>
                <p className="text-xs text-gray-500">p.{source.page} · 관련도 {Math.round(source.score * 100)}%</p>
              </div>
              <button
                onClick={() => setPreviewOpen(false)}
                className="text-gray-400 hover:text-gray-600 text-xl leading-none px-2"
              >
                ×
              </button>
            </div>
            <div className="p-2">
              <img
                src={pagePreviewUrl}
                alt={`${source.filename} p.${source.page}`}
                className="w-full rounded"
              />
            </div>
          </div>
        </div>
      )}
    </>
  )
}
