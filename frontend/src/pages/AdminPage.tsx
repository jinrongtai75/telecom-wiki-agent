import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../services/api'
import { useAuth } from '../contexts/AuthContext'
import type { UserInfo } from '../types'

export default function AdminPage() {
  const { isAdmin } = useAuth()
  const navigate = useNavigate()

  const [users, setUsers] = useState<UserInfo[]>([])
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newIsAdmin, setNewIsAdmin] = useState(false)
  const [createMsg, setCreateMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [creating, setCreating] = useState(false)

  const [llmMode, setLlmMode] = useState<'fast' | 'thinking'>('fast')
  const [llmSaving, setLlmSaving] = useState(false)

  const myId = (() => {
    try {
      const token = sessionStorage.getItem('access_token')
      if (!token) return ''
      const payload = JSON.parse(atob(token.split('.')[1]))
      return payload.sub as string
    } catch {
      return ''
    }
  })()

  useEffect(() => {
    if (!isAdmin) {
      navigate('/search')
      return
    }
    api.getUsers().then((r) => setUsers(r.data))
    api.getLlmMode().then((r) => setLlmMode(r.data.mode as 'fast' | 'thinking')).catch(() => {})
  }, [isAdmin, navigate])

  const handleSetLlmMode = async (mode: 'fast' | 'thinking') => {
    setLlmSaving(true)
    try {
      await api.setLlmMode(mode)
      setLlmMode(mode)
    } finally {
      setLlmSaving(false)
    }
  }

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreateMsg(null)
    setCreating(true)
    try {
      const res = await api.createUser(newUsername, newPassword, newIsAdmin)
      setUsers((u) => [...u, res.data])
      setNewUsername('')
      setNewPassword('')
      setNewIsAdmin(false)
      setCreateMsg({ ok: true, text: `'${res.data.username}' 계정이 생성되었습니다` })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setCreateMsg({ ok: false, text: msg ?? '계정 생성에 실패했습니다' })
    } finally {
      setCreating(false)
    }
  }

  const handleDeleteUser = async (id: string, username: string) => {
    if (!confirm(`'${username}' 계정을 삭제하시겠습니까?`)) return
    try {
      await api.deleteUser(id)
      setUsers((u) => u.filter((x) => x.id !== id))
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg ?? '삭제 실패')
    }
  }

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' })

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
          <h1 className="text-sm font-bold text-white">관리자 패널</h1>
        </div>
        <button
          onClick={() => window.open(import.meta.env.VITE_PREPROCESSOR_URL ?? 'http://localhost:1024', '_blank')}
          className="flex items-center gap-1.5 text-xs bg-[#E6007E]/15 hover:bg-[#E6007E]/25 text-[#E6007E] px-3 py-1.5 rounded-lg transition-colors"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
            <polyline points="15 3 21 3 21 9" />
            <line x1="10" y1="14" x2="21" y2="3" />
          </svg>
          전처리 도구
        </button>
      </header>

      <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">

        {/* LLM 모드 설정 */}
        <section>
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">LLM 모드</h2>
          <div className="bg-[#161622] rounded-xl border border-white/8 p-5">
            <p className="text-xs text-gray-500 mb-4">
              RAG 검색 답변 생성에 사용할 LLM 동작 모드를 선택합니다.<br />
              빠른 모드는 응답 속도가 빠르고, 사고 모드는 복잡한 질문에 더 정확합니다.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => handleSetLlmMode('fast')}
                disabled={llmSaving}
                className={`flex-1 flex flex-col items-center gap-1.5 px-4 py-3 rounded-xl border text-sm font-medium transition-all disabled:opacity-40 ${
                  llmMode === 'fast'
                    ? 'bg-[#E6007E]/15 border-[#E6007E]/50 text-[#E6007E]'
                    : 'bg-white/5 border-white/10 text-gray-400 hover:border-white/25 hover:text-gray-200'
                }`}
              >
                <span className="text-lg">⚡</span>
                <span>빠른 모드</span>
                <span className="text-xs font-normal opacity-70">thinking 비활성화</span>
              </button>
              <button
                onClick={() => handleSetLlmMode('thinking')}
                disabled={llmSaving}
                className={`flex-1 flex flex-col items-center gap-1.5 px-4 py-3 rounded-xl border text-sm font-medium transition-all disabled:opacity-40 ${
                  llmMode === 'thinking'
                    ? 'bg-[#E6007E]/15 border-[#E6007E]/50 text-[#E6007E]'
                    : 'bg-white/5 border-white/10 text-gray-400 hover:border-white/25 hover:text-gray-200'
                }`}
              >
                <span className="text-lg">🧠</span>
                <span>사고 모드</span>
                <span className="text-xs font-normal opacity-70">extended thinking</span>
              </button>
            </div>
            {llmSaving && <p className="text-xs text-gray-500 mt-3 text-center">저장 중…</p>}
          </div>
        </section>

        {/* 새 사용자 추가 */}
        <section>
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">새 사용자 추가</h2>
          <div className="bg-[#161622] rounded-xl border border-white/8 p-5">
            <form onSubmit={handleCreateUser} className="space-y-4">
              <div className="flex flex-wrap gap-3">
                <div className="flex-1 min-w-32">
                  <label className="block text-xs text-gray-500 mb-1.5">아이디</label>
                  <input
                    type="text"
                    value={newUsername}
                    onChange={(e) => setNewUsername(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-[#E6007E]/60 focus:border-[#E6007E]/60 transition-colors"
                    placeholder="최소 3자"
                    required
                    minLength={3}
                  />
                </div>
                <div className="flex-1 min-w-32">
                  <label className="block text-xs text-gray-500 mb-1.5">패스워드</label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-[#E6007E]/60 focus:border-[#E6007E]/60 transition-colors"
                    placeholder="최소 6자"
                    required
                    minLength={6}
                  />
                </div>
              </div>

              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2.5 cursor-pointer select-none">
                  <div
                    onClick={() => setNewIsAdmin((v) => !v)}
                    className={`w-9 h-5 rounded-full transition-colors relative ${newIsAdmin ? 'bg-[#E6007E]' : 'bg-white/15'}`}
                  >
                    <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${newIsAdmin ? 'translate-x-4' : 'translate-x-0.5'}`} />
                  </div>
                  <span className="text-sm text-gray-300">관리자 권한</span>
                </label>

                <button
                  type="submit"
                  disabled={creating}
                  className="bg-[#E6007E] hover:bg-[#c4006b] text-white px-5 py-2 rounded-lg text-sm font-medium disabled:opacity-40 transition-colors"
                >
                  {creating ? '생성 중…' : '추가'}
                </button>
              </div>
            </form>

            {createMsg && (
              <div className={`mt-3 text-xs px-3 py-2 rounded-lg ${
                createMsg.ok
                  ? 'bg-green-500/15 text-green-400 border border-green-500/20'
                  : 'bg-red-500/15 text-red-400 border border-red-500/20'
              }`}>
                {createMsg.ok ? '✓ ' : '✕ '}{createMsg.text}
              </div>
            )}
          </div>
        </section>

        {/* 사용자 목록 */}
        <section>
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            전체 사용자 <span className="text-gray-600 normal-case">({users.length}명)</span>
          </h2>
          <div className="space-y-2">
            {users.map((u) => (
              <div
                key={u.id}
                className="bg-[#161622] rounded-xl border border-white/8 px-4 py-3.5 flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  {/* 아바타 */}
                  <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-xs font-bold text-gray-300 flex-shrink-0">
                    {u.username[0].toUpperCase()}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-100">{u.username}</span>
                      {u.is_admin && (
                        <span className="text-xs bg-[#E6007E]/15 text-[#E6007E] px-1.5 py-0.5 rounded">관리자</span>
                      )}
                      {u.id === myId && (
                        <span className="text-xs bg-white/8 text-gray-500 px-1.5 py-0.5 rounded">나</span>
                      )}
                    </div>
                    <p className="text-xs text-gray-600 mt-0.5">가입일 {formatDate(u.created_at)}</p>
                  </div>
                </div>
                <button
                  onClick={() => handleDeleteUser(u.id, u.username)}
                  disabled={u.id === myId}
                  className="text-xs text-gray-600 hover:text-red-400 disabled:opacity-20 disabled:cursor-not-allowed transition-colors ml-4"
                >
                  삭제
                </button>
              </div>
            ))}
            {users.length === 0 && (
              <p className="text-center text-gray-600 py-8 text-sm">사용자가 없습니다</p>
            )}
          </div>
        </section>

      </div>
    </div>
  )
}
