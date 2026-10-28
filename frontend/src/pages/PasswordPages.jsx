import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api.js'

const fieldError = (err, key) => (err?.data?.[key] ? [].concat(err.data[key]).join(' ') : '')

/** Ask for a reset link. The reply is the same whether or not the account exists. */
export function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const res = await api('/auth/password/forgot/', { method: 'POST', body: { email }, auth: false })
      setMessage(res.detail)
    } catch (err) {
      setError(err.status === 429 ? 'Too many requests. Please wait a while and try again.' : fieldError(err, 'email') || err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main>
      <h1>Forgot password</h1>
      {message ? (
        <p role="status">{message} Check your inbox; the link works once and expires in 1 hour.</p>
      ) : (
        <form onSubmit={onSubmit}>
          <p>Enter the email address of your ASIMS account and we will email you a link to choose a new password.</p>
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          {error && <p role="alert">{error}</p>}
          <button type="submit" disabled={busy}>Send reset link</button>
        </form>
      )}
      <p><Link to="/login">Back to login</Link></p>
    </main>
  )
}

/** Choose a password from an emailed link (a reset, or a staff invitation). */
export function ResetPassword() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    if (password !== confirm) {
      setError('The two passwords do not match.')
      return
    }
    setBusy(true)
    try {
      const res = await api('/auth/password/reset/', { method: 'POST', body: { token, new_password: password }, auth: false })
      setDone(res.detail)
    } catch (err) {
      setError(fieldError(err, 'new_password') || err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!token) {
    return (
      <main>
        <h1>Set your password</h1>
        <p role="alert">This page needs the link from your email.</p>
        <Link to="/forgot-password">Ask for a new link</Link>
      </main>
    )
  }
  return (
    <main>
      <h1>Set your password</h1>
      {done ? (
        <p role="status">{done} <Link to="/login">Go to login</Link></p>
      ) : (
        <form onSubmit={onSubmit}>
          <label>
            New password
            <input type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          <label>
            Repeat the new password
            <input type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
          </label>
          <p>At least 8 characters, not only numbers, and not a common password or close to your name or email.</p>
          {error && <p role="alert">{error}</p>}
          <button type="submit" disabled={busy}>Set password</button>
          {error.includes('link') && <p><Link to="/forgot-password">Ask for a new link</Link></p>}
        </form>
      )}
    </main>
  )
}

/** A logged-in user of any role changes their own password. */
export function ChangePassword() {
  const [current, setCurrent] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [errors, setErrors] = useState({})
  const [done, setDone] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setErrors({})
    setDone('')
    if (password !== confirm) {
      setErrors({ confirm: 'The two new passwords do not match.' })
      return
    }
    setBusy(true)
    try {
      const res = await api('/auth/password/change/', { method: 'POST', body: { current_password: current, new_password: password } })
      setDone(res.detail)
      setCurrent('')
      setPassword('')
      setConfirm('')
    } catch (err) {
      setErrors({ current: fieldError(err, 'current_password'), password: fieldError(err, 'new_password'),
        detail: err.data?.current_password || err.data?.new_password ? '' : err.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <main>
      <p><Link to="/dashboard">Dashboard</Link></p>
      <h1>Change password</h1>
      {done && <p role="status">{done}</p>}
      <form onSubmit={onSubmit}>
        <label>
          Current password
          <input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
        </label>
        {errors.current && <p role="alert">{errors.current}</p>}
        <label>
          New password
          <input type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        {errors.password && <p role="alert">{errors.password}</p>}
        <label>
          Repeat the new password
          <input type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
        </label>
        {errors.confirm && <p role="alert">{errors.confirm}</p>}
        {errors.detail && <p role="alert">{errors.detail}</p>}
        <button type="submit" disabled={busy}>Change password</button>
      </form>
    </main>
  )
}
