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
  const [createMsg, setCreateMsg] = useState('')
  const [creating, setCreating] = useState(false)

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
  }, [isAdmin, navigate])

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreateMsg('')
    setCreating(true)
    try {
      const res = await api.createUser(newUsername, newPassword, newIsAdmin)
      setUsers((u) => [...u, res.data])
      setNewUsername('')
      setNewPassword('')
      setNewIsAdmin(false)
      setCreateMsg(`✅ '${res.data.username}' 계정 생성 완료`)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setCreateMsg(`❌ ${msg ?? '계정 생성 실패'}`)
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
    <div className="min-h-screen bg-gray-50">
      <header className="bg-lgu-dark text-white px-4 py-3 flex items-center justify-between">
        <h1 className="font-bold text-sm">관리자</h1>
        <div className="flex items-center gap-2">
          <button
            className="text-xs bg-white/20 px-3 py-1 rounded cursor-default"
          >
            사용자 관리
          </button>
          <button
            onClick={() => window.open(import.meta.env.VITE_PREPROCESSOR_URL ?? 'http://localhost:1024', '_blank')}
            className="text-xs bg-purple-500 hover:bg-purple-400 text-white px-3 py-1 rounded transition-colors"
          >
            전처리 도구 열기
          </button>
          <button
            onClick={() => navigate('/search')}
            className="text-xs bg-white/10 hover:bg-white/20 px-3 py-1 rounded transition-colors"
          >
            검색으로
          </button>
        </div>
      </header>

      <div className="max-w-2xl mx-auto px-4 py-6">
        {/* 새 사용자 추가 */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">새 사용자 추가</h2>
          <form onSubmit={handleCreateUser} className="flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-32">
              <label className="block text-xs text-gray-500 mb-1">아이디</label>
              <input
                type="text"
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-lgu-pink"
                placeholder="최소 3자"
                required
                minLength={3}
              />
            </div>
            <div className="flex-1 min-w-32">
              <label className="block text-xs text-gray-500 mb-1">패스워드</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-lgu-pink"
                placeholder="최소 6자"
                required
                minLength={6}
              />
            </div>
            <div className="flex items-center gap-2 pb-2">
              <input
                id="is-admin"
                type="checkbox"
                checked={newIsAdmin}
                onChange={(e) => setNewIsAdmin(e.target.checked)}
                className="accent-lgu-pink"
              />
              <label htmlFor="is-admin" className="text-sm text-gray-600">관리자</label>
            </div>
            <button
              type="submit"
              disabled={creating}
              className="bg-lgu-pink text-white px-5 py-2 rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {creating ? '생성 중...' : '추가'}
            </button>
          </form>
          {createMsg && <p className="mt-3 text-sm text-gray-600">{createMsg}</p>}
        </div>

        {/* 사용자 목록 */}
        <div className="space-y-2">
          <h2 className="text-sm font-medium text-gray-700 mb-3">전체 사용자 ({users.length}명)</h2>
          {users.map((u) => (
            <div key={u.id} className="bg-white rounded-lg border border-gray-100 px-4 py-3 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-800">{u.username}</span>
                  {u.is_admin && (
                    <span className="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">관리자</span>
                  )}
                  {u.id === myId && (
                    <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">나</span>
                  )}
                </div>
                <p className="text-xs text-gray-400 mt-0.5">가입일 {formatDate(u.created_at)}</p>
              </div>
              <button
                onClick={() => handleDeleteUser(u.id, u.username)}
                disabled={u.id === myId}
                className="text-xs text-red-400 hover:text-red-600 disabled:opacity-30 disabled:cursor-not-allowed ml-4"
              >
                삭제
              </button>
            </div>
          ))}
          {users.length === 0 && (
            <p className="text-center text-gray-400 py-8 text-sm">사용자가 없습니다</p>
          )}
        </div>
      </div>
    </div>
  )
}
