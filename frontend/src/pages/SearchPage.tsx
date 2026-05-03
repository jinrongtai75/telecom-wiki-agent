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

const SUGGESTIONS = [
  { icon: '📡', text: '5G NR 핸드오버 절차를 단계별로 설명해줘' },
  { icon: '🔗', text: 'LTE 베어러 설정 과정은 어떻게 되나요?' },
  { icon: '📶', text: 'RRC 연결 수립 절차를 상세히 알려줘' },
  { icon: '🧩', text: 'PDCP와 RLC 계층의 역할 차이점은?' },
]

// ── SVG icons ──────────────────────────────────────────────────────────────

function IconSend() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  )
}

function IconStop() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  )
}

function IconHistory() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <polyline points="12 8 12 12 14 14" />
      <path d="M3.05 11a9 9 0 1 0 .5-4.5" />
      <polyline points="3 3 3 7 7 7" />
    </svg>
  )
}

function IconSettings() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  )
}

function IconLogout() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  )
}

function IconSignal() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <path d="M1.5 8.5a13 13 0 0 1 21 0" />
      <path d="M5 12a10 10 0 0 1 14 0" />
      <path d="M8.5 15.5a6 6 0 0 1 7 0" />
      <circle cx="12" cy="19" r="1" fill="currentColor" />
    </svg>
  )
}

// ── AI avatar ──────────────────────────────────────────────────────────────

function AIAvatar() {
  return (
    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-[#E6007E] to-[#9b0050] flex items-center justify-center shadow-md">
      <IconSignal />
    </div>
  )
}

// ── Streaming cursor ────────────────────────────────────────────────────────

function Cursor() {
  return <span className="inline-block w-0.5 h-4 bg-[#E6007E] animate-cursor-blink ml-0.5 align-middle" />
}

// ── Thinking dots ──────────────────────────────────────────────────────────

function ThinkingDots() {
  return (
    <div className="flex gap-1.5 py-1">
      <span className="w-2 h-2 bg-[#E6007E]/60 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
      <span className="w-2 h-2 bg-[#E6007E]/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
      <span className="w-2 h-2 bg-[#E6007E]/60 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
    </div>
  )
}

// ── Welcome screen ─────────────────────────────────────────────────────────

function WelcomeScreen({ onSuggest }: { onSuggest: (text: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center flex-1 px-6 py-12 select-none">
      {/* Logo + title */}
      <div className="flex items-center gap-3 mb-3">
        <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-[#E6007E] to-[#9b0050] flex items-center justify-center shadow-lg shadow-[#E6007E]/20">
          <IconSignal />
        </div>
        <div className="text-left">
          <h1 className="text-xl font-bold text-white leading-tight">무선통신프로토콜</h1>
          <p className="text-sm text-gray-400 leading-tight">위키백과사전 에이전트</p>
        </div>
      </div>

      <p className="text-gray-400 text-sm text-center mt-2 mb-10 max-w-md">
        LGU+ 기술규격서 기반 RAG 검색 · Gemini 2.5 Flash 답변 생성
      </p>

      {/* Suggestion cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-2xl">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.text}
            onClick={() => onSuggest(s.text)}
            className="flex items-start gap-3 p-4 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 hover:border-[#E6007E]/40 transition-all text-left group"
          >
            <span className="text-xl mt-0.5">{s.icon}</span>
            <span className="text-sm text-gray-300 group-hover:text-white transition-colors leading-snug">{s.text}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function SearchPage() {
  const { apiToken, isAdmin, logout } = useAuth()
  const navigate = useNavigate()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const stopRef = useRef<(() => void) | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }, [input])

  const handleSend = useCallback(() => {
    if (!input.trim() || loading) return

    const question = input.trim()
    setInput('')
    setError('')

    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: question }
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
            msg.id === assistantId ? { ...msg, response: { ...msg.response, sources: event.data } } : msg,
          ),
        )
      } else if (event.type === 'token') {
        setMessages((m) =>
          m.map((msg) =>
            msg.id === assistantId ? { ...msg, content: msg.content + event.data } : msg,
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
        setMessages((m) => m.map((msg) => (msg.id === assistantId ? { ...msg, streaming: false } : msg)))
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
    <div className="flex h-screen bg-[#0f0f17] text-white overflow-hidden">

      {/* ── Sidebar ─────────────────────────────────────────────────── */}
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={`
          fixed md:relative inset-y-0 left-0 z-30 w-64 bg-[#161622] flex flex-col
          transition-transform duration-300 ease-in-out
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        `}
      >
        {/* Brand */}
        <div className="p-5 border-b border-white/5">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#E6007E] to-[#9b0050] flex items-center justify-center shadow-md flex-shrink-0">
              <IconSignal />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-bold text-white truncate">무선통신프로토콜</p>
              <p className="text-xs text-gray-500 truncate">위키백과사전</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-1">
          <button
            onClick={() => { setMessages([]); setError(''); setSidebarOpen(false) }}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium bg-[#E6007E]/15 text-[#E6007E] hover:bg-[#E6007E]/20 transition-colors"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" className="w-4 h-4">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            새 대화
          </button>

          <button
            onClick={() => { navigate('/history'); setSidebarOpen(false) }}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
          >
            <IconHistory />
            대화 히스토리
          </button>

          {isAdmin && (
            <button
              onClick={() => { navigate('/admin'); setSidebarOpen(false) }}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
            >
              <IconSettings />
              관리자 패널
            </button>
          )}
        </nav>

        {/* Bottom */}
        <div className="p-3 border-t border-white/5 space-y-2">
          {/* API key panel */}
          <div className="px-1">
            <AuthKeyPanel compact />
          </div>

          {/* API key missing warning */}
          {!apiToken && (
            <div className="px-3 py-2 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-xs text-yellow-400">
              API 키 미설정 — 답변 생성 불가
            </div>
          )}

          <button
            onClick={logout}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-500 hover:text-gray-300 hover:bg-white/5 transition-colors"
          >
            <IconLogout />
            로그아웃
          </button>
        </div>
      </aside>

      {/* ── Main area ───────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">

        {/* Mobile top bar */}
        <div className="md:hidden flex items-center justify-between px-4 py-3 border-b border-white/5 bg-[#161622]">
          <button onClick={() => setSidebarOpen(true)} className="text-gray-400 hover:text-white p-1">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5">
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
          <span className="text-sm font-medium text-white">무선통신프로토콜 위키</span>
          <div className="w-7" /> {/* spacer */}
        </div>

        {/* Messages scroll area */}
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {messages.length === 0 ? (
            <WelcomeScreen onSuggest={(text) => { setInput(text); textareaRef.current?.focus() }} />
          ) : (
            <div className="max-w-3xl mx-auto px-4 py-6 space-y-8">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}

              {error && (
                <div className="flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-sm text-red-400">
                  <span className="text-lg leading-none">⚠</span>
                  <span>{error}</span>
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {/* Input area */}
        <div className="px-4 pb-5 pt-3 bg-[#0f0f17]">
          <div className="max-w-3xl mx-auto">
            <div className={`
              relative flex items-end gap-3 rounded-2xl border px-4 py-3
              bg-[#1a1a2e] transition-colors
              ${loading ? 'border-white/10' : 'border-white/15 focus-within:border-[#E6007E]/50'}
            `}>
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="무선통신 프로토콜에 대해 질문하세요…"
                className="flex-1 bg-transparent text-sm text-gray-100 placeholder-gray-500 resize-none outline-none leading-relaxed min-h-[24px] max-h-40 py-0.5"
                rows={1}
                disabled={loading}
              />
              {loading ? (
                <button
                  onClick={handleStop}
                  className="flex-shrink-0 w-9 h-9 rounded-xl bg-white/10 hover:bg-white/20 flex items-center justify-center text-gray-300 transition-colors"
                  title="생성 중지"
                >
                  <IconStop />
                </button>
              ) : (
                <button
                  onClick={handleSend}
                  disabled={!input.trim()}
                  className="flex-shrink-0 w-9 h-9 rounded-xl bg-[#E6007E] hover:bg-[#c4006b] disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center text-white transition-colors"
                  title="전송 (Enter)"
                >
                  <IconSend />
                </button>
              )}
            </div>
            <p className="text-center text-xs text-gray-600 mt-2">
              Enter 전송 · Shift+Enter 줄바꿈
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}

// ── Message bubble component ───────────────────────────────────────────────

function MessageBubble({ message: msg }: { message: Message }) {
  if (msg.role === 'user') {
    return (
      <div className="flex justify-end gap-3">
        <div className="max-w-[75%] bg-[#1e1e35] border border-white/10 rounded-2xl rounded-tr-sm px-4 py-3 text-sm text-gray-100 leading-relaxed whitespace-pre-wrap">
          {msg.content}
        </div>
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-xs font-bold text-gray-300 mt-0.5">
          나
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-3">
      <AIAvatar />
      <div className="flex-1 min-w-0 space-y-3 pt-0.5">
        {/* Sources */}
        {msg.response && msg.response.sources.length > 0 && (
          <div>
            <p className="text-xs text-gray-500 mb-2 font-medium tracking-wide uppercase">참고 자료</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {msg.response.sources.slice(0, 4).map((src, i) => (
                <SourceCard key={i} source={src} dark />
              ))}
            </div>
          </div>
        )}

        {/* Content */}
        <div className="text-sm text-gray-200 leading-relaxed">
          {msg.content ? (
            <div className="prose-dark prose prose-sm max-w-none">
              <ReactMarkdown>{msg.content}</ReactMarkdown>
              {msg.streaming && <Cursor />}
            </div>
          ) : (
            <ThinkingDots />
          )}
        </div>
      </div>
    </div>
  )
}
