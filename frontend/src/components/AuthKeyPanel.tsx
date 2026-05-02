import { useState, useEffect, useRef } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { api } from '../services/api'

export default function AuthKeyPanel() {
  const { geminiToken, setApiConfig, isAdmin } = useAuth()
  const [open, setOpen] = useState(false)
  const [geminiInput, setGeminiInput] = useState('')
  const [dbKeys, setDbKeys] = useState<Record<string, boolean>>({})
  const [saving, setSaving] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    api.listKeys().then((res) => setDbKeys(res.data)).catch(() => {})
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

  const handleSave = async () => {
    setSaving(true)
    try {
      if (geminiInput && isAdmin) {
        await api.saveKey('GEMINI', geminiInput).catch(() => {})
      }
      setApiConfig(geminiInput)
      const res = await api.listKeys().catch(() => ({ data: dbKeys }))
      setDbKeys(res.data)
    } finally {
      setSaving(false)
      setGeminiInput('')
      setOpen(false)
    }
  }

  const geminiSaved = !!(geminiToken || dbKeys['gemini'])

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className={`text-xs px-2 py-1 rounded transition-colors ${
          open ? 'bg-white/30' : 'bg-white/10 hover:bg-white/20'
        }`}
      >
        API 키
        {geminiSaved && (
          <span className="ml-1 w-1.5 h-1.5 inline-block rounded-full bg-green-400 align-middle" />
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1.5 bg-white border border-gray-200 rounded-xl shadow-xl p-4 z-50 w-72">
          <h3 className="text-xs font-semibold text-gray-700 mb-3">Gemini API 키 설정</h3>

          <div className="mb-4">
            <label className="block text-xs text-gray-500 mb-1">
              Gemini API Key <span className="text-gray-400">(LLM + 임베딩)</span>
              {geminiSaved && <span className="ml-1 text-green-600 text-xs">✓ 설정됨</span>}
            </label>
            <input
              type="password"
              value={geminiInput}
              onChange={(e) => setGeminiInput(e.target.value)}
              placeholder={geminiSaved ? '변경하려면 새 키 입력' : 'Google API 키 입력'}
              className="w-full border rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-lgu-pink"
            />
            {!isAdmin && (
              <p className="text-xs text-gray-400 mt-1">입력하지 않으면 관리자가 설정한 공유 키를 사용합니다.</p>
            )}
          </div>

          <button
            onClick={handleSave}
            disabled={saving}
            className="w-full bg-lgu-pink text-white py-1.5 rounded-lg text-xs font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {saving ? '저장 중...' : '저장'}
          </button>
        </div>
      )}
    </div>
  )
}
