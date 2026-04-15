import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { api } from '../services/api'
import type { HistoryItem } from '../types'
import SourceCard from '../components/SourceCard'
import AuthKeyPanel from '../components/AuthKeyPanel'

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
    <div className="min-h-screen bg-gray-50">
      <header className="bg-lgu-dark text-white px-4 py-3 flex items-center justify-between">
        <h1 className="font-bold text-sm">검색 히스토리</h1>
        <div className="flex items-center gap-2">
          {history.length > 0 && (
            <button onClick={deleteAll} className="text-xs text-red-300 hover:text-red-100">
              전체 삭제
            </button>
          )}
          <button onClick={() => navigate('/search')} className="text-xs bg-white/10 hover:bg-white/20 px-2 py-1 rounded transition-colors">
            검색으로
          </button>
          <AuthKeyPanel />
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-4 py-4 space-y-3">
        {loading && <p className="text-center text-gray-400 py-8">불러오는 중...</p>}
        {!loading && history.length === 0 && (
          <p className="text-center text-gray-400 py-8">검색 히스토리가 없습니다</p>
        )}

        {history.map((item) => (
          <div key={item.id} className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <button
              onClick={() => setExpanded(expanded === item.id ? null : item.id)}
              className="w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-gray-800 line-clamp-2">{item.question}</p>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className="text-xs text-gray-400">
                    {new Date(item.created_at).toLocaleDateString('ko-KR')}
                  </span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${item.provider === 'jihye' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'}`}>
                    {item.provider}
                  </span>
                </div>
              </div>
            </button>

            {expanded === item.id && (
              <div className="px-4 pb-4 border-t border-gray-50">
                <div className="prose prose-sm max-w-none text-gray-700 mt-3">
                  <ReactMarkdown>{item.answer}</ReactMarkdown>
                </div>
                {item.sources.length > 0 && (
                  <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {item.sources.slice(0, 4).map((src, i) => (
                      <SourceCard key={i} source={src} />
                    ))}
                  </div>
                )}
                <div className="mt-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">답변이 도움이 됐나요?</span>
                    <button
                      onClick={() => handleFeedback(item.id, 1)}
                      disabled={!!feedbacks[item.id] || feedbackLoading === item.id}
                      className={`text-sm px-2 py-0.5 rounded transition-colors ${feedbacks[item.id] === 1 ? 'bg-green-100 text-green-700' : 'text-gray-400 hover:text-green-600 hover:bg-green-50'} disabled:cursor-default`}
                    >
                      👍
                    </button>
                    <button
                      onClick={() => handleFeedback(item.id, -1)}
                      disabled={!!feedbacks[item.id] || feedbackLoading === item.id}
                      className={`text-sm px-2 py-0.5 rounded transition-colors ${feedbacks[item.id] === -1 ? 'bg-red-100 text-red-700' : 'text-gray-400 hover:text-red-600 hover:bg-red-50'} disabled:cursor-default`}
                    >
                      👎
                    </button>
                  </div>
                  <button
                    onClick={() => deleteOne(item.id)}
                    className="text-xs text-red-400 hover:text-red-600"
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
