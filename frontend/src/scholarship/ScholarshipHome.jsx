import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { STATUS_LABELS } from './options.js'
import './scholarship.css'

const date = (d) => new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

/** Student's starting point: open cycles to apply to and their existing applications. */
export default function ScholarshipHome() {
  const navigate = useNavigate()
  const [cycles, setCycles] = useState(null)
  const [applications, setApplications] = useState(null)
  const [error, setError] = useState('')
  const [starting, setStarting] = useState(null)

  useEffect(() => {
    Promise.all([api('/scholarships/cycles/open/'), api('/scholarships/applications/')])
      .then(([open, mine]) => {
        setCycles(open)
        setApplications(mine.results)
      })
      .catch((err) => setError(err.message))
  }, [])

  async function start(cycle) {
    setStarting(cycle.id)
    setError('')
    try {
      const app = await api('/scholarships/applications/', { method: 'POST', body: { cycle: cycle.id } })
      navigate(`/scholarships/${app.id}/personal`)
    } catch (err) {
      setError(err.message)
      setStarting(null)
    }
  }

  if (error && !cycles) return <main className="sch-page"><p className="field-error" role="alert">{error}</p></main>
  if (!cycles) return <main className="sch-page"><p>Loading...</p></main>

  const appliedCycles = new Set(applications.map((a) => a.cycle))
  const available = cycles.filter((c) => !appliedCycles.has(c.id))

  return (
    <main className="sch-page">
      <p className="crumbs"><Link to="/dashboard">Dashboard</Link></p>
      <h1>Scholarship applications</h1>
      {error && <p className="field-error" role="alert">{error}</p>}

      <h2>My applications</h2>
      {applications.length === 0 ? <p>You have not started an application yet.</p> : (
        <ul className="cards">
          {applications.map((a) => (
            <li key={a.id} className="card">
              <p className="card-title">{a.cycle_name} · Application {a.id}</p>
              <p>Status: <strong>{STATUS_LABELS[a.status]}</strong></p>
              <p className="field-hint">
                {a.submitted_at ? `Submitted ${date(a.submitted_at)}` : `Last saved ${date(a.updated_at)}`}
              </p>
              <Link className="button" to={`/scholarships/${a.id}/${a.status === 'draft' ? 'personal' : a.status === 'returned' ? 'review' : 'status'}`}>
                {a.status === 'draft' ? 'Continue' : a.status === 'returned' ? 'Make corrections' : 'View status'}
              </Link>
            </li>
          ))}
        </ul>
      )}

      <h2>Open for applications</h2>
      {available.length === 0 ? <p>No other scholarship cycle is open right now.</p> : (
        <ul className="cards">
          {available.map((c) => (
            <li key={c.id} className="card">
              <p className="card-title">{c.name}</p>
              <p className="field-hint">Open until {date(c.closes_on)}</p>
              <button type="button" disabled={starting === c.id} onClick={() => start(c)}>
                {starting === c.id ? 'Starting...' : 'Start application'}
              </button>
            </li>
          ))}
        </ul>
      )}
    </main>
  )
}
