import { createContext, useContext, useState, type ReactNode } from 'react'
import type { AuthState } from '../types'

interface AuthContextValue extends AuthState {
  login: (token: string, isAdmin: boolean) => void
  logout: () => void
  setApiConfig: (provider: 'jihye' | 'gemini', jihyeToken: string, geminiToken: string) => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const savedProvider = (sessionStorage.getItem('provider') as 'jihye' | 'gemini') ?? 'jihye'
  // Support legacy 'api_token' key for jihye (backwards compat)
  const savedJihye = sessionStorage.getItem('jihye_token') ?? (savedProvider === 'jihye' ? sessionStorage.getItem('api_token') : null)
  const savedGemini = sessionStorage.getItem('gemini_token') ?? (savedProvider === 'gemini' ? sessionStorage.getItem('api_token') : null)
  const computedApiToken = savedProvider === 'jihye' ? savedJihye : savedGemini

  const [state, setState] = useState<AuthState>({
    accessToken: sessionStorage.getItem('access_token'),
    isAdmin: sessionStorage.getItem('is_admin') === 'true',
    apiToken: computedApiToken,
    provider: savedProvider,
    jihyeToken: savedJihye,
    geminiToken: savedGemini,
  })

  const login = (token: string, isAdmin: boolean) => {
    sessionStorage.setItem('access_token', token)
    sessionStorage.setItem('is_admin', String(isAdmin))
    setState((s) => ({ ...s, accessToken: token, isAdmin }))
  }

  const logout = () => {
    sessionStorage.clear()
    setState({ accessToken: null, isAdmin: false, apiToken: null, provider: 'jihye', jihyeToken: null, geminiToken: null })
  }

  const setApiConfig = (provider: 'jihye' | 'gemini', newJihye: string, newGemini: string) => {
    sessionStorage.setItem('provider', provider)
    const jihye = newJihye || sessionStorage.getItem('jihye_token') || null
    const gemini = newGemini || sessionStorage.getItem('gemini_token') || null
    if (newJihye) sessionStorage.setItem('jihye_token', newJihye)
    if (newGemini) sessionStorage.setItem('gemini_token', newGemini)
    const apiToken = provider === 'jihye' ? jihye : gemini
    if (apiToken) sessionStorage.setItem('api_token', apiToken)
    setState((s) => ({
      ...s,
      provider,
      jihyeToken: jihye,
      geminiToken: gemini,
      apiToken,
    }))
  }

  return (
    <AuthContext.Provider value={{ ...state, login, logout, setApiConfig }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
