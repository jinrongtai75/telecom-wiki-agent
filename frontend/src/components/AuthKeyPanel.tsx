import { useState, useEffect, useRef } from 'react'
import { useAuth } from '../contexts/AuthContext'

export default function AuthKeyPanel() {
  const { provider, jihyeToken, geminiToken, setApiConfig } = useAuth()
  const [open, setOpen] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState<'jihye' | 'gemini'>(provider)
  const [jihyeInput, setJihyeInput] = useState('')
  const [geminiInput, setGeminiInput] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)

  // Sync provider when context changes
  useEffect(() => {
    setSelectedProvider(provider)
  }, [provider])

  useEffect(() => {
    if (!open) return
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleEsc)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEsc)
    }
  }, [open])

  const handleSave = () => {
    setApiConfig(selectedProvider, jihyeInput, geminiInput)
    setJihyeInput('')
    setGeminiInput('')
    setOpen(false)
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className={`text-xs px-2 py-1 rounded transition-colors ${
          open ? 'bg-white/30' : 'bg-white/10 hover:bg-white/20'
        }`}
      >
        인증키
        {(jihyeToken || geminiToken) && (
          <span className="ml-1 w-1.5 h-1.5 inline-block rounded-full bg-green-400 align-middle" />
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1.5 bg-white border border-gray-200 rounded-xl shadow-xl p-4 z-50 w-72">
          <h3 className="text-xs font-semibold text-gray-700 mb-3">인증키 설정</h3>

          {/* 프로바이더 선택 */}
          <div className="mb-3">
            <label className="block text-xs text-gray-500 mb-1.5">사용 프로바이더</label>
            <div className="flex gap-4">
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="radio"
                  name="auth-provider"
                  value="jihye"
                  checked={selectedProvider === 'jihye'}
                  onChange={() => setSelectedProvider('jihye')}
                  className="accent-lgu-pink"
                />
                <span className="text-xs">JIHYE Gateway</span>
              </label>
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="radio"
                  name="auth-provider"
                  value="gemini"
                  checked={selectedProvider === 'gemini'}
                  onChange={() => setSelectedProvider('gemini')}
                  className="accent-lgu-pink"
                />
                <span className="text-xs">Google Gemini</span>
              </label>
            </div>
          </div>

          {/* JIHYE 토큰 */}
          <div className="mb-3">
            <label className="block text-xs text-gray-500 mb-1">
              JIHYE 토큰
              {jihyeToken && <span className="ml-1 text-green-600 text-xs">✓ 설정됨</span>}
            </label>
            <input
              type="password"
              value={jihyeInput}
              onChange={(e) => setJihyeInput(e.target.value)}
              placeholder={jihyeToken ? '변경하려면 새 토큰 입력' : 'JWT 토큰 입력'}
              className="w-full border rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-lgu-pink"
            />
          </div>

          {/* Gemini API Key */}
          <div className="mb-4">
            <label className="block text-xs text-gray-500 mb-1">
              Gemini API Key
              {geminiToken && <span className="ml-1 text-green-600 text-xs">✓ 설정됨</span>}
            </label>
            <input
              type="password"
              value={geminiInput}
              onChange={(e) => setGeminiInput(e.target.value)}
              placeholder={geminiToken ? '변경하려면 새 키 입력' : 'Google API 키 입력'}
              className="w-full border rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-lgu-pink"
            />
          </div>

          <button
            onClick={handleSave}
            className="w-full bg-lgu-pink text-white py-1.5 rounded-lg text-xs font-medium hover:opacity-90 transition-opacity"
          >
            저장
          </button>
        </div>
      )}
    </div>
  )
}
