import { useState } from 'react'
import type { SourceInfo } from '../types'
import PdfPageViewer from './PdfPageViewer'

export default function SourceCard({ source, dark = false }: { source: SourceInfo; dark?: boolean }) {
  const [previewOpen, setPreviewOpen] = useState(false)

  const externalUrl = source.from_3gpp && source.section ? source.section : null
  const hasPdfPreview = !source.from_3gpp && !!source.doc_id && !!source.has_pdf

  const isClickable = !!(externalUrl || hasPdfPreview)

  const handleClick = () => {
    if (externalUrl) {
      window.open(externalUrl, '_blank', 'noopener,noreferrer')
    } else if (hasPdfPreview) {
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
        title={externalUrl ? '클릭하여 3GPP 규격 열기' : hasPdfPreview ? '클릭하여 문서 미리보기' : undefined}
      >
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
            {hasPdfPreview && <span className="text-xs text-[#E6007E]">미리보기 →</span>}
          </div>
        </div>
      </div>

      {/* PDF 전체 문서 뷰어 모달 */}
      {previewOpen && source.doc_id && (
        <div
          className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-3"
          onClick={() => setPreviewOpen(false)}
        >
          <div
            className="bg-[#1e1e35] border border-white/10 rounded-xl shadow-2xl flex flex-col"
            style={{ width: '90vw', height: '92vh' }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* 헤더 */}
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/10 flex-shrink-0">
              <div className="min-w-0">
                <p className="text-sm font-medium text-gray-200 truncate">{source.filename}</p>
                <p className="text-xs text-gray-500">p.{source.page} 위치에서 열기 · 관련도 {Math.round(source.score * 100)}%</p>
              </div>
              <button
                onClick={() => setPreviewOpen(false)}
                className="text-gray-500 hover:text-gray-300 text-2xl leading-none pl-4 flex-shrink-0"
              >
                ×
              </button>
            </div>

            {/* PDF 뷰어: min-h-0 + flex flex-col 필수 — PdfPageViewer의 flex-1/overflow-y-auto가 동작하려면 부모가 flex container여야 함 */}
            <div className="flex-1 min-h-0 flex flex-col">
              <PdfPageViewer
                docId={source.doc_id}
                totalPages={0}
                chunks={[]}
                selectedChunkId={null}
                scrollToPage={source.page}
                selectMode={false}
                onChunkSelect={() => {}}
                onRegionSelect={() => {}}
              />
            </div>
          </div>
        </div>
      )}
    </>
  )
}
