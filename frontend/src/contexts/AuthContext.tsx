import { createContext, useContext, useState, type ReactNode } from 'react'
import type { AuthState } from '../types'

interface AuthContextValue extends AuthState {
  login: (token: string, isAdmin: boolean) => void
  logout: () => void
  setApiConfig: (geminiToken: string) => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const savedGemini = sessionStorage.getItem('gemini_token')

  const [state, setState] = useState<AuthState>({
    accessToken: sessionStorage.getItem('access_token'),
    isAdmin: sessionStorage.getItem('is_admin') === 'true',
    apiToken: savedGemini,
    provider: 'gemini',
    geminiToken: savedGemini,
  })

  const login = (token: string, isAdmin: boolean) => {
    sessionStorage.setItem('access_token', token)
    sessionStorage.setItem('is_admin', String(isAdmin))
    setState((s) => ({ ...s, accessToken: token, isAdmin }))
  }

  const logout = () => {
    sessionStorage.clear()
    setState({ accessToken: null, isAdmin: false, apiToken: null, provider: 'gemini', geminiToken: null })
  }

  const setApiConfig = (geminiToken: string) => {
    const token = geminiToken || sessionStorage.getItem('gemini_token') || null
    if (geminiToken) sessionStorage.setItem('gemini_token', geminiToken)
    setState((s) => ({
      ...s,
      provider: 'gemini',
      geminiToken: token,
      apiToken: token,
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
