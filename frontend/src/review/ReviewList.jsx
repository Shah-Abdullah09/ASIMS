import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../AuthContext.jsx'
import { STATUS_LABELS } from '../scholarship/options.js'
import '../scholarship/scholarship.css'
import { completionText } from './format.js'
import { PLACEMENT, QUEUES } from './roles.js'

const FILTERS = ['cycle', 'department', 'status', 'complete', 'search', 'ordering', 'page']
const date = (d) => (d ? new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—')

/** A staff member's work queue. The Placement Office sees every case with filters and can forward shortlisted
cases in bulk; the DAC and approvers see the cases waiting for them. Filters stay in the address bar. */
export default function ReviewList() {
  const { user } = useAuth()
  const isPlacement = PLACEMENT.includes(user.role)
  const queue = QUEUES[user.role] || QUEUES.placement_officer
  const [params, setParams] = useSearchParams()
  const [refresh, setRefresh] = useState(0)
  const [forwardMsg, setForwardMsg] = useState('')
  const [cycles, setCycles] = useState([])
  const [departments, setDepartments] = useState([])
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [search, setSearch] = useState(params.get('search') || '')
  const query = params.toString()

  useEffect(() => {
    api('/scholarships/cycles/').then(setCycles).catch(() => setCycles([]))
    api('/departments/', { auth: false }).then(setDepartments).catch(() => setDepartments([]))
  }, [])

  useEffect(() => {
    let current = true
    api(`/scholarships/review/applications/${query ? `?${query}` : ''}`)
      .then((d) => current && (setData(d), setError('')))
      .catch((e) => current && setError(e.message))
    return () => { current = false }
  }, [query, refresh])

  async function forwardAll() {
    const cycle = params.get('cycle')
    const scope = cycle ? ` of ${cycles.find((c) => String(c.id) === cycle)?.name || 'this cycle'}` : ''
    if (!window.confirm(`Forward every shortlisted case${scope} awaiting forwarding to the Director?`)) return
    setForwardMsg('')
    try {
      const result = await api('/scholarships/review/applications/forward-all/',
        { method: 'POST', body: { confirm: true, cycle: cycle ? Number(cycle) : null } })
      const n = result.forwarded.length
      setForwardMsg(n ? `Forwarded ${n} case${n === 1 ? '' : 's'} to the Director.` : 'No cases were awaiting forwarding.')
      setRefresh((x) => x + 1)
    } catch (err) {
      setForwardMsg(err.message)
    }
  }

  function setFilter(name, value) {
    const next = new URLSearchParams(params)
    if (value) next.set(name, value)
    else next.delete(name)
    if (name !== 'page') next.delete('page') // new filter -> back to the first page
    setParams(next)
  }

  const page = Number(params.get('page') || 1)
  const filtered = FILTERS.some((f) => f !== 'page' && f !== 'ordering' && params.get(f))

  return (
    <main className="sch-page">
      <p className="crumbs"><Link to="/dashboard">Dashboard</Link></p>
      <h1>{queue.title}</h1>
      <p className="field-hint">{queue.hint}</p>
      {isPlacement && (
        <div className="actions">
          <button type="button" onClick={forwardAll}>Forward all shortlisted to the Director</button>
          {forwardMsg && <p role="status" className="notice-ok">{forwardMsg}</p>}
        </div>
      )}

      <form className="filters" role="search" onSubmit={(e) => { e.preventDefault(); setFilter('search', search.trim()) }}>
        <label>
          Search
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Name, Registration ID, CNIC or email" />
        </label>
        <button type="submit">Search</button>
        <label>
          Cycle
          <select value={params.get('cycle') || ''} onChange={(e) => setFilter('cycle', e.target.value)}>
            <option value="">All cycles</option>
            {cycles.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        {isPlacement && <label>
          Department
          <select value={params.get('department') || ''} onChange={(e) => setFilter('department', e.target.value)}>
            <option value="">All departments</option>
            {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </label>}
        {isPlacement && <label>
          Status
          <select value={params.get('status') || ''} onChange={(e) => setFilter('status', e.target.value)}>
            <option value="">All statuses</option>
            {Object.keys(STATUS_LABELS).filter((s) => s !== 'draft').map((s) => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
          </select>
        </label>}
        <label>
          Completeness
          <select value={params.get('complete') || ''} onChange={(e) => setFilter('complete', e.target.value)}>
            <option value="">Complete and incomplete</option>
            <option value="true">Complete only</option>
            <option value="false">Incomplete only</option>
          </select>
        </label>
        <label>
          Sort by
          <select value={params.get('ordering') || '-submitted_at'} onChange={(e) => setFilter('ordering', e.target.value)}>
            <option value="-submitted_at">Newest first</option>
            <option value="submitted_at">Oldest first</option>
            <option value="applicant_name">Name A-Z</option>
          </select>
        </label>
        {filtered && (
          <button type="button" className="secondary" onClick={() => { setSearch(''); setParams(new URLSearchParams()) }}>
            Clear filters
          </button>
        )}
      </form>

      {error && <p className="field-error" role="alert">{error}</p>}
      {!data ? <p>Loading...</p> : (
        <>
          <p role="status">{data.count} application{data.count === 1 ? '' : 's'}{filtered ? ' match the filters' : ''}.</p>
          {data.results.length > 0 && (
            <div className="table-scroll">
              <table className="list-table">
                <thead>
                  <tr>
                    <th scope="col">No.</th>
                    <th scope="col">Applicant</th>
                    <th scope="col">Registration ID</th>
                    <th scope="col">Department</th>
                    <th scope="col">Cycle</th>
                    <th scope="col">Status</th>
                    <th scope="col">Submitted</th>
                    <th scope="col">Completeness</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((a) => (
                    <tr key={a.id}>
                      <td>{a.id}</td>
                      <td><Link to={`/review/${a.id}`}>{a.applicant_name || a.email}</Link></td>
                      <td>{a.registration_id || '—'}</td>
                      <td>{a.department || '—'}</td>
                      <td>{a.cycle_name}</td>
                      <td><span className={`chip chip-${a.status}`}>{STATUS_LABELS[a.status]}</span></td>
                      <td>{date(a.submitted_at)}</td>
                      <td className={a.completion.complete ? 'text-ok' : 'text-warn'}>{completionText(a.completion)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {(data.previous || data.next) && (
            <nav className="actions" aria-label="Pages">
              <button type="button" className="secondary" disabled={!data.previous} onClick={() => setFilter('page', String(page - 1))}>
                Previous
              </button>
              <span>Page {page}</span>
              <button type="button" className="secondary" disabled={!data.next} onClick={() => setFilter('page', String(page + 1))}>
                Next
              </button>
            </nav>
          )}
        </>
      )}
    </main>
  )
}
