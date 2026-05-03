import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { api } from '../services/api'
import type { HistoryItem } from '../types'
import SourceCard from '../components/SourceCard'

export default function HistoryPage() {
  const navigate = useNavigate()
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [feedbacks, setFeedbacks] = useState<Record<string, 1 | -1>>({})
  const [feedbackLoading, setFeedbackLoading] = useState<string | null>(null)

  useEffect(() => {
    api.getHistory().then((r) => {
      setHistory(r.data)
      setLoading(false)
    })
  }, [])

  const deleteOne = async (id: string) => {
    await api.deleteHistory(id)
    setHistory((h) => h.filter((x) => x.id !== id))
  }

  const deleteAll = async () => {
    if (!confirm('모든 히스토리를 삭제하시겠습니까?')) return
    await api.deleteAllHistory()
    setHistory([])
  }

  const handleFeedback = async (id: string, rating: 1 | -1) => {
    if (feedbackLoading || feedbacks[id]) return
    setFeedbackLoading(id)
    try {
      await api.submitFeedback(id, rating)
      setFeedbacks((f) => ({ ...f, [id]: rating }))
    } catch {
      // 실패 시 무시
    } finally {
      setFeedbackLoading(null)
    }
  }

  return (
    <div className="min-h-screen bg-[#0f0f17] text-white">
      {/* 헤더 */}
      <header className="bg-[#161622] border-b border-white/5 px-4 py-3 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/search')}
            className="text-gray-400 hover:text-white transition-colors p-1"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
              <path d="M19 12H5M12 5l-7 7 7 7" />
            </svg>
          </button>
          <div>
            <h1 className="text-sm font-bold text-white">대화 히스토리</h1>
            {!loading && history.length > 0 && (
              <p className="text-xs text-gray-500">{history.length}개 대화</p>
            )}
          </div>
        </div>
        {history.length > 0 && (
          <button
            onClick={deleteAll}
            className="text-xs text-red-400 hover:text-red-300 transition-colors px-2 py-1 rounded hover:bg-red-500/10"
          >
            전체 삭제
          </button>
        )}
      </header>

      {/* 콘텐츠 */}
      <div className="max-w-3xl mx-auto px-4 py-6 space-y-3">
        {loading && (
          <div className="flex items-center justify-center py-16 gap-2">
            <span className="w-2 h-2 bg-[#E6007E]/60 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-2 h-2 bg-[#E6007E]/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-2 h-2 bg-[#E6007E]/60 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
        )}

        {!loading && history.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-gray-600">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-12 h-12 mb-3 opacity-40">
              <polyline points="12 8 12 12 14 14" />
              <path d="M3.05 11a9 9 0 1 0 .5-4.5" />
              <polyline points="3 3 3 7 7 7" />
            </svg>
            <p className="text-sm">대화 히스토리가 없습니다</p>
          </div>
        )}

        {history.map((item) => (
          <div
            key={item.id}
            className="bg-[#161622] rounded-xl border border-white/8 overflow-hidden"
          >
            {/* 질문 행 — 클릭하면 펼치기 */}
            <button
              onClick={() => setExpanded(expanded === item.id ? null : item.id)}
              className="w-full text-left px-4 py-3.5 hover:bg-white/3 transition-colors"
            >
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm text-gray-200 line-clamp-2 leading-relaxed">{item.question}</p>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className="text-xs text-gray-600">
                    {new Date(item.created_at).toLocaleDateString('ko-KR')}
                  </span>
                  <span className="text-xs px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400">
                    {item.provider}
                  </span>
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    className={`w-4 h-4 text-gray-600 transition-transform duration-200 ${expanded === item.id ? 'rotate-180' : ''}`}
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </div>
              </div>
            </button>

            {/* 펼쳐진 답변 */}
            {expanded === item.id && (
              <div className="px-4 pb-4 border-t border-white/5">
                {/* 출처 */}
                {item.sources.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs text-gray-600 mb-2 font-medium tracking-wide uppercase">참고 자료</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {item.sources.slice(0, 4).map((src, i) => (
                        <SourceCard key={i} source={src} dark />
                      ))}
                    </div>
                  </div>
                )}

                {/* 답변 */}
                <div className="prose-dark prose prose-sm max-w-none mt-3">
                  <ReactMarkdown>{item.answer}</ReactMarkdown>
                </div>

                {/* 피드백 + 삭제 */}
                <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-600">도움이 됐나요?</span>
                    <button
                      onClick={() => handleFeedback(item.id, 1)}
                      disabled={!!feedbacks[item.id] || feedbackLoading === item.id}
                      className={`text-sm px-2 py-0.5 rounded transition-colors disabled:cursor-default ${
                        feedbacks[item.id] === 1
                          ? 'bg-green-500/20 text-green-400'
                          : 'text-gray-500 hover:text-green-400 hover:bg-green-500/10'
                      }`}
                    >
                      👍
                    </button>
                    <button
                      onClick={() => handleFeedback(item.id, -1)}
                      disabled={!!feedbacks[item.id] || feedbackLoading === item.id}
                      className={`text-sm px-2 py-0.5 rounded transition-colors disabled:cursor-default ${
                        feedbacks[item.id] === -1
                          ? 'bg-red-500/20 text-red-400'
                          : 'text-gray-500 hover:text-red-400 hover:bg-red-500/10'
                      }`}
                    >
                      👎
                    </button>
                  </div>
                  <button
                    onClick={() => deleteOne(item.id)}
                    className="text-xs text-gray-600 hover:text-red-400 transition-colors"
                  >
                    삭제
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
