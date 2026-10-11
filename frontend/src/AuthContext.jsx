import { createContext, useContext, useEffect, useState } from 'react'
import { api, loadTokens, saveTokens } from './api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(() => Boolean(loadTokens()))

  // Restore the session from a stored token on first load
  useEffect(() => {
    if (!loadTokens()) return
    api('/auth/me/')
      .then(setUser)
      .catch(() => saveTokens(null))
      .finally(() => setLoading(false))
  }, [])

  async function login(email, password) {
    const data = await api('/auth/login/', { method: 'POST', body: { email, password }, auth: false })
    saveTokens({ access: data.access, refresh: data.refresh })
    setUser(data.user)
    return data.user
  }

  function logout() {
    saveTokens(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
