import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../AuthContext.jsx'
import '../scholarship/scholarship.css'

const when = (d) => new Date(d).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })

/** The signed-in person's notifications and their email switch. */
export default function NotificationsPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [emailOn, setEmailOn] = useState(user.email_notifications !== false)
  const [saved, setSaved] = useState('')

  const load = useCallback(() => api('/notifications/').then(setData).catch((e) => setError(e.message)), [])
  useEffect(() => { load() }, [load])

  async function open(note) {
    if (!note.read_at) await api(`/notifications/${note.id}/read/`, { method: 'POST' }).catch(() => {})
    if (note.link) navigate(note.link)
    else load()
  }

  async function readAll() {
    await api('/notifications/read-all/', { method: 'POST' })
    load()
  }

  async function toggleEmail(value) {
    setSaved('')
    try {
      const me = await api('/auth/me/', { method: 'PATCH', body: { email_notifications: value } })
      setEmailOn(me.email_notifications)
      setSaved(me.email_notifications ? 'You will also get these by email.' : 'Email copies are off. You will still see them here.')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <main className="sch-page">
      <p className="crumbs"><Link to="/dashboard">Dashboard</Link></p>
      <h1>Notifications</h1>
      <label className="checkbox">
        <input type="checkbox" checked={emailOn} onChange={(e) => toggleEmail(e.target.checked)} />
        Also send me these by email
      </label>
      {saved && <p className="notice-ok" role="status">{saved}</p>}
      {error && <p className="field-error" role="alert">{error}</p>}
      {!data ? <p>Loading...</p> : (
        <>
          <div className="actions">
            <p>{data.unread ? `${data.unread} unread` : 'All read.'}</p>
            {data.unread > 0 && <button type="button" className="secondary" onClick={readAll}>Mark all as read</button>}
          </div>
          {data.results.length === 0 ? <p>No notifications yet.</p> : (
            <ul className="notification-list">
              {data.results.map((note) => (
                <li key={note.id} className={note.read_at ? 'read' : 'unread'}>
                  <button type="button" className="notification" onClick={() => open(note)}>
                    <span className="notification-title">{note.title}</span>
                    {note.body && <span className="notification-body">{note.body}</span>}
                    <span className="field-hint">{when(note.created_at)}{note.read_at ? '' : ' · new'}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </main>
  )
}
