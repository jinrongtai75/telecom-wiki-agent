import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import { useAuth } from '../contexts/AuthContext'
import { searchStream } from '../services/api'
import SourceCard from '../components/SourceCard'
import AuthKeyPanel from '../components/AuthKeyPanel'
import type { SearchResponse, SourceInfo } from '../types'
import { useNavigate } from 'react-router-dom'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  response?: Partial<SearchResponse> & { sources: SourceInfo[] }
}

export default function SearchPage() {
  const { apiToken, isAdmin, logout } = useAuth()
  const navigate = useNavigate()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const stopRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = useCallback(() => {
    if (!input.trim() || loading) return

    const question = input.trim()
    setInput('')
    setError('')

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: question,
    }

    const assistantId = (Date.now() + 1).toString()
    const assistantMsg: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      streaming: true,
      response: { sources: [] },
    }

    setMessages((m) => [...m, userMsg, assistantMsg])
    setLoading(true)

    const stop = searchStream(question, 'gemini', apiToken ?? '', (event) => {
      if (event.type === 'sources') {
        setMessages((m) =>
          m.map((msg) =>
            msg.id === assistantId
              ? { ...msg, response: { ...msg.response, sources: event.data } }
              : msg,
          ),
        )
      } else if (event.type === 'token') {
        setMessages((m) =>
          m.map((msg) =>
            msg.id === assistantId
              ? { ...msg, content: msg.content + event.data }
              : msg,
          ),
        )
      } else if (event.type === 'done') {
        setMessages((m) =>
          m.map((msg) =>
            msg.id === assistantId
              ? { ...msg, streaming: false, response: { sources: msg.response?.sources ?? [], history_id: event.data.history_id } }
              : msg,
          ),
        )
        setLoading(false)
      } else if (event.type === 'error') {
        setError(event.data)
        setMessages((m) =>
          m.map((msg) =>
            msg.id === assistantId ? { ...msg, streaming: false } : msg,
          ),
        )
        setLoading(false)
      }
    })

    stopRef.current = stop
  }, [input, loading, apiToken])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleStop = () => {
    stopRef.current?.()
    setLoading(false)
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* 헤더 */}
      <header className="bg-lgu-dark text-white px-4 py-3 flex items-center justify-between">
        <div>
          <h1 className="font-bold text-sm">무선통신프로토콜 위키백과사전</h1>
          <p className="text-xs text-gray-400">Google Gemini</p>
        </div>
        <div className="flex items-center gap-3">
          {isAdmin && (
            <button
              onClick={() => navigate('/admin')}
              className="text-xs bg-white/10 hover:bg-white/20 px-2 py-1 rounded transition-colors"
            >
              관리자
            </button>
          )}
          <button
            onClick={() => navigate('/history')}
            className="text-xs bg-white/10 hover:bg-white/20 px-2 py-1 rounded transition-colors"
          >
            히스토리
          </button>
          <button
            onClick={logout}
            className="text-xs text-gray-400 hover:text-white transition-colors"
          >
            로그아웃
          </button>
          <AuthKeyPanel />
        </div>
      </header>

      {/* 인증키 미설정 경고 */}
      {!apiToken && (
        <div className="bg-yellow-50 border-b border-yellow-200 text-yellow-800 text-xs px-4 py-2 flex items-center gap-2">
          <span>⚠</span>
          <span>Gemini API 키가 설정되지 않았습니다. 우측 상단 <strong>API 키</strong> 버튼에서 입력하거나 관리자에게 문의하세요.</span>
        </div>
      )}

      {/* 메시지 영역 */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center mt-16 text-gray-400">
            <p className="text-lg font-medium">무선통신 프로토콜에 대해 질문하세요</p>
            <p className="text-sm mt-2">예: "5G NR 핸드오버 절차를 설명해줘"</p>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-3xl w-full ${msg.role === 'user' ? 'ml-12' : 'mr-12'}`}>
              {msg.role === 'user' ? (
                <div className="bg-lgu-pink text-white px-4 py-3 rounded-2xl rounded-tr-sm text-sm ml-auto max-w-lg">
                  {msg.content}
                </div>
              ) : (
                <div className="space-y-3">
                  {/* 출처 먼저 표시 (스트리밍 중에도) */}
                  {msg.response && msg.response.sources.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-400 mb-2">참고 자료</p>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {msg.response.sources.slice(0, 4).map((src, i) => (
                          <SourceCard key={i} source={src} />
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="bg-white px-4 py-3 rounded-2xl rounded-tl-sm shadow-sm border border-gray-100">
                    {msg.content ? (
                      <div className="prose prose-sm max-w-none text-gray-800">
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                        {msg.streaming && (
                          <span className="inline-block w-2 h-4 bg-lgu-pink animate-pulse ml-0.5 align-middle" />
                        )}
                      </div>
                    ) : (
                      <div className="flex gap-1">
                        <span className="w-2 h-2 bg-lgu-pink rounded-full animate-bounce" />
                        <span className="w-2 h-2 bg-lgu-pink rounded-full animate-bounce [animation-delay:0.2s]" />
                        <span className="w-2 h-2 bg-lgu-pink rounded-full animate-bounce [animation-delay:0.4s]" />
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* 입력 영역 */}
      <div className="bg-white border-t px-4 py-3">
        <div className="flex gap-2 max-w-4xl mx-auto">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="질문을 입력하세요 (Shift+Enter: 줄바꿈, Enter: 전송)"
            className="flex-1 border rounded-xl px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-lgu-pink"
            rows={2}
            disabled={loading}
          />
          {loading ? (
            <button
              onClick={handleStop}
              className="bg-gray-500 text-white px-4 rounded-xl font-medium hover:opacity-90 transition-opacity self-end py-2 text-sm"
            >
              중지
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              className="bg-lgu-pink text-white px-4 rounded-xl font-medium hover:opacity-90 disabled:opacity-50 transition-opacity self-end py-2 text-sm"
            >
              전송
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
