import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import ManageNav from './ManageNav.jsx'

const day = (d) => (d ? new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—')
const when = (d) => new Date(d).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
const messages = (err) => (err?.data && typeof err.data === 'object'
  ? Object.values(err.data).flat().join(' ') : err.message)

function Page({ title, children }) {
  return (
    <main className="sch-page">
      <p className="crumbs"><Link to="/dashboard">Dashboard</Link> / Manage</p>
      <h1>{title}</h1>
      <ManageNav />
      {children}
    </main>
  )
}

/** Departments: add, rename, activate or deactivate (students register into active departments). */
export function ManageDepartments() {
  const [rows, setRows] = useState(null)
  const [form, setForm] = useState({ name: '', code: '' })
  const [error, setError] = useState('')
  const load = useCallback(() => api('/admin/departments/').then((d) => setRows(d.results ?? d)), [])
  useEffect(() => { load().catch((e) => setError(e.message)) }, [load])

  async function call(path, method, body) {
    setError('')
    try {
      await api(path, { method, body })
      await load()
      return true
    } catch (err) {
      setError(messages(err))
      return false
    }
  }

  return (
    <Page title="Departments">
      <form className="filters" aria-label="Add a department"
        onSubmit={async (e) => { e.preventDefault(); if (await call('/admin/departments/', 'POST', form)) setForm({ name: '', code: '' }) }}>
        <label>Name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></label>
        <label>Code<input value={form.code} maxLength={10} onChange={(e) => setForm({ ...form, code: e.target.value })} required /></label>
        <button type="submit">Add department</button>
      </form>
      {error && <p className="field-error" role="alert">{error}</p>}
      {!rows ? <p>Loading...</p> : (
        <div className="table-scroll">
          <table className="list-table">
            <thead><tr><th scope="col">Code</th><th scope="col">Name</th><th scope="col">Status</th><th scope="col">Actions</th></tr></thead>
            <tbody>
              {rows.map((d) => (
                <tr key={d.id}>
                  <td>{d.code}</td><td>{d.name}</td><td>{d.is_active ? 'Active' : 'Inactive'}</td>
                  <td>
                    <button type="button" className="secondary"
                      onClick={() => call(`/admin/departments/${d.id}/`, 'PATCH', { is_active: !d.is_active })}>
                      {d.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Page>
  )
}

/** Scholarship cycles: open a new one, change dates, close; a cycle without applications can be deleted. */
export function ManageCycles() {
  const [rows, setRows] = useState(null)
  const [form, setForm] = useState({ name: '', opens_on: '', closes_on: '' })
  const [editing, setEditing] = useState(null)
  const [error, setError] = useState('')
  const load = useCallback(() => api('/admin/cycles/').then((d) => setRows(d.results ?? d)), [])
  useEffect(() => { load().catch((e) => setError(e.message)) }, [load])

  async function call(path, method, body) {
    setError('')
    try {
      await api(path, { method, body })
      await load()
      return true
    } catch (err) {
      setError(messages(err))
      return false
    }
  }

  return (
    <Page title="Scholarship cycles">
      <form className="filters" aria-label="Open a new cycle"
        onSubmit={async (e) => { e.preventDefault(); if (await call('/admin/cycles/', 'POST', form)) setForm({ name: '', opens_on: '', closes_on: '' }) }}>
        <label>Name<input value={form.name} placeholder="e.g. Spring-27" onChange={(e) => setForm({ ...form, name: e.target.value })} required /></label>
        <label>Opens on<input type="date" value={form.opens_on} onChange={(e) => setForm({ ...form, opens_on: e.target.value })} required /></label>
        <label>Closes on<input type="date" value={form.closes_on} onChange={(e) => setForm({ ...form, closes_on: e.target.value })} required /></label>
        <button type="submit">Add cycle</button>
      </form>
      {error && <p className="field-error" role="alert">{error}</p>}
      {!rows ? <p>Loading...</p> : (
        <div className="table-scroll">
          <table className="list-table">
            <thead><tr><th scope="col">Cycle</th><th scope="col">Opens</th><th scope="col">Closes</th><th scope="col">Status</th><th scope="col">Applications</th><th scope="col">Actions</th></tr></thead>
            <tbody>
              {rows.map((c) => (editing?.id === c.id ? (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td><input type="date" aria-label={`Opening date of ${c.name}`} value={editing.opens_on} onChange={(e) => setEditing({ ...editing, opens_on: e.target.value })} /></td>
                  <td><input type="date" aria-label={`Closing date of ${c.name}`} value={editing.closes_on} onChange={(e) => setEditing({ ...editing, closes_on: e.target.value })} /></td>
                  <td>{c.is_active ? 'Open' : 'Closed'}</td><td>{c.applications}</td>
                  <td>
                    <button type="button" onClick={async () => { if (await call(`/admin/cycles/${c.id}/`, 'PATCH', { opens_on: editing.opens_on, closes_on: editing.closes_on })) setEditing(null) }}>Save</button>{' '}
                    <button type="button" className="secondary" onClick={() => setEditing(null)}>Cancel</button>
                  </td>
                </tr>
              ) : (
                <tr key={c.id}>
                  <td>{c.name}</td><td>{day(c.opens_on)}</td><td>{day(c.closes_on)}</td>
                  <td>{c.is_active ? 'Open' : 'Closed'}</td><td>{c.applications}</td>
                  <td>
                    <button type="button" className="secondary" onClick={() => setEditing({ id: c.id, opens_on: c.opens_on, closes_on: c.closes_on })}>Change dates</button>{' '}
                    <button type="button" className="secondary" onClick={() => call(`/admin/cycles/${c.id}/`, 'PATCH', { is_active: !c.is_active })}>
                      {c.is_active ? 'Close' : 'Reopen'}
                    </button>{' '}
                    {c.applications === 0 && (
                      <button type="button" className="link-button"
                        onClick={() => window.confirm(`Delete the ${c.name} cycle?`) && call(`/admin/cycles/${c.id}/`, 'DELETE')}>Delete</button>
                    )}
                  </td>
                </tr>
              )))}
            </tbody>
          </table>
        </div>
      )}
    </Page>
  )
}

/** The audit log: who did what and when, filtered by action, person and dates. Read-only. */
export function AuditLogPage() {
  const [actions, setActions] = useState([])
  const [filters, setFilters] = useState({ action: '', actor: '', date_from: '', date_to: '' })
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => { api('/admin/audit-log/actions/').then(setActions).catch(() => {}) }, [])
  const load = useCallback(() => {
    const params = new URLSearchParams(Object.entries(filters).filter(([, v]) => v))
    if (page > 1) params.set('page', page)
    return api(`/admin/audit-log/?${params}`).then(setData).catch((e) => setError(e.message))
  }, [filters, page])
  useEffect(() => { load() }, [load])

  const set = (k) => (e) => { setPage(1); setFilters((f) => ({ ...f, [k]: e.target.value })) }
  return (
    <Page title="Audit log">
      <p className="field-hint">Every login, change and decision, newest first. Entries cannot be changed or deleted.</p>
      <form className="filters" role="search" onSubmit={(e) => e.preventDefault()}>
        <label>Action
          <select value={filters.action} onChange={set('action')}>
            <option value="">All actions</option>
            {actions.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
          </select>
        </label>
        <label>Person<input type="search" value={filters.actor} onChange={set('actor')} placeholder="Name or email" /></label>
        <label>From<input type="date" value={filters.date_from} onChange={set('date_from')} /></label>
        <label>To<input type="date" value={filters.date_to} onChange={set('date_to')} /></label>
      </form>
      {error && <p className="field-error" role="alert">{error}</p>}
      {!data ? <p>Loading...</p> : (
        <>
          <p role="status">{data.count} entr{data.count === 1 ? 'y' : 'ies'}.</p>
          <div className="table-scroll">
            <table className="list-table">
              <thead><tr><th scope="col">When</th><th scope="col">Who</th><th scope="col">Action</th><th scope="col">Record</th><th scope="col">Details</th><th scope="col">IP</th></tr></thead>
              <tbody>
                {data.results.map((e) => (
                  <tr key={e.id}>
                    <td>{when(e.created_at)}</td>
                    <td>{e.actor_name || '—'}<br /><span className="field-hint">{e.actor || ''}{e.actor_role ? ` · ${e.actor_role.replace('_', ' ')}` : ''}</span></td>
                    <td>{e.action_label}</td>
                    <td>{e.target_type ? `${e.target_type.split('.')[1]} ${e.target_id}` : '—'}</td>
                    <td className="audit-details">{Object.entries(e.details).map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`).join('; ')}</td>
                    <td>{e.ip_address || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(data.previous || data.next) && (
            <nav className="actions" aria-label="Pages">
              <button type="button" className="secondary" disabled={!data.previous} onClick={() => setPage(page - 1)}>Previous</button>
              <span>Page {page}</span>
              <button type="button" className="secondary" disabled={!data.next} onClick={() => setPage(page + 1)}>Next</button>
            </nav>
          )}
        </>
      )}
    </Page>
  )
}
