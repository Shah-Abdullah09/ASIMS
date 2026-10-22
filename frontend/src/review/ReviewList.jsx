import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api.js'
import { STATUS_LABELS } from '../scholarship/options.js'
import '../scholarship/scholarship.css'
import { completionText } from './format.js'

const FILTERS = ['cycle', 'department', 'status', 'complete', 'search', 'ordering', 'page']
const date = (d) => (d ? new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—')

/** Placement Office list of submitted applications with filters and search (kept in the address bar). */
export default function ReviewList() {
  const [params, setParams] = useSearchParams()
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
  }, [query])

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
      <h1>Scholarship applications</h1>
      <p className="field-hint">Submitted Need Based Financial Grant applications. Drafts are not shown.</p>

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
        <label>
          Department
          <select value={params.get('department') || ''} onChange={(e) => setFilter('department', e.target.value)}>
            <option value="">All departments</option>
            {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </label>
        <label>
          Status
          <select value={params.get('status') || ''} onChange={(e) => setFilter('status', e.target.value)}>
            <option value="">All statuses</option>
            {['pending', 'under_review', 'approved', 'rejected'].map((s) => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
          </select>
        </label>
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
