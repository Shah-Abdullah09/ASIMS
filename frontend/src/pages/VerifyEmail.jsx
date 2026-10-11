import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api.js'

export default function VerifyEmail() {
  const [params] = useSearchParams()
  const token = params.get('token')
  const [message, setMessage] = useState(token ? 'Verifying...' : 'Missing verification token.')

  useEffect(() => {
    if (!token) return
    api('/auth/verify-email/', { method: 'POST', body: { token }, auth: false })
      .then((res) => setMessage(res.detail))
      .catch((err) => setMessage(err.message))
  }, [token])

  return (
    <main>
      <h1>Email verification</h1>
      <p>{message}</p>
      <Link to="/login">Go to login</Link>
    </main>
  )
}
