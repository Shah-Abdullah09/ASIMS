import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api } from '../api.js'

/** Header link to the notifications page with the unread count, refreshed on each page change and every minute. */
export default function NotificationBell() {
  const location = useLocation()
  const [unread, setUnread] = useState(0)

  useEffect(() => {
    let current = true
    const refresh = () => api('/notifications/?unread=true')
      .then((data) => current && setUnread(Number(data?.unread) || 0))
      .catch(() => {})
    refresh()
    const timer = setInterval(refresh, 60_000)
    return () => { current = false; clearInterval(timer) }
  }, [location.pathname])

  return (
    <Link className="header-bell" to="/notifications"
      aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'}>
      <span aria-hidden="true">🔔</span>
      {unread > 0 && <span className="bell-count" aria-hidden="true">{unread > 99 ? '99+' : unread}</span>}
    </Link>
  )
}
