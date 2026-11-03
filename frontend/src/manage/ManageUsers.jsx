import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { DEPARTMENT_ROLES, ROLE_LABELS } from '../roles.js'
import ManageNav from './ManageNav.jsx'

const fieldErrors = (err) => (err?.data && typeof err.data === 'object'
  ? Object.fromEntries(Object.entries(err.data).map(([k, v]) => [k, [].concat(v).join(' ')]))
  : { detail: err.message })

/** One user: role, department and active can be changed; staff can be sent a new set-password invitation. */
function UserRow({ user, departments, onSaved }) {
  const [editing, setEditing] = useState(false)
  const [role, setRole] = useState(user.role)
  const [department, setDepartment] = useState(user.department ?? '')
  const [active, setActive] = useState(user.is_active)
  const [errors, setErrors] = useState({})
  const [note, setNote] = useState('')

  async function save() {
    setErrors({})
    try {
      onSaved(await api(`/admin/users/${user.id}/`, { method: 'PATCH',
        body: { role, department: department === '' ? null : Number(department), is_active: active } }))
      setEditing(false)
      setNote('Saved.')
    } catch (err) {
      setErrors(fieldErrors(err))
    }
  }

  async function invite() {
    setNote('')
    try {
      setNote((await api(`/admin/users/${user.id}/invite/`, { method: 'POST' })).detail)
    } catch (err) {
      setNote(err.message)
    }
  }

  const deptName = departments.find((d) => d.id === user.department)?.name
  return (
    <tr>
      <td>{user.full_name}<br /><span className="field-hint">{user.email}</span></td>
      {editing ? (
        <>
          <td>
            <select aria-label={`Role of ${user.email}`} value={role} onChange={(e) => setRole(e.target.value)}>
              {Object.entries(ROLE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            {errors.role && <p className="field-error">{errors.role}</p>}
          </td>
          <td>
            <select aria-label={`Department of ${user.email}`} value={department} onChange={(e) => setDepartment(e.target.value)}>
              <option value="">None</option>
              {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
            {errors.department && <p className="field-error">{errors.department}</p>}
          </td>
          <td>
            <label className="checkbox"><input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} /> Active</label>
          </td>
          <td>
            <button type="button" onClick={save}>Save</button>{' '}
            <button type="button" className="secondary" onClick={() => setEditing(false)}>Cancel</button>
            {errors.detail && <p className="field-error">{errors.detail}</p>}
          </td>
        </>
      ) : (
        <>
          <td>{ROLE_LABELS[user.role]}</td>
          <td>{deptName || '—'}</td>
          <td>{user.is_active ? 'Active' : 'Deactivated'}</td>
          <td>
            <button type="button" className="secondary" onClick={() => { setEditing(true); setNote('') }}>Edit</button>{' '}
            {user.role !== 'student' && user.is_active && (
              <button type="button" className="secondary" onClick={invite}>Send invitation</button>
            )}
            {note && <p className="field-hint" role="status">{note}</p>}
          </td>
        </>
      )}
    </tr>
  )
}

/** The Administrator creates staff accounts (by emailed invitation) and manages everyone's role and access. */
export default function ManageUsers() {
  const [users, setUsers] = useState(null)
  const [departments, setDepartments] = useState([])
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [form, setForm] = useState({ email: '', full_name: '', role: 'placement_officer', department: '', password: '' })
  const [errors, setErrors] = useState({})
  const [created, setCreated] = useState('')

  const load = useCallback(() => {
    const params = new URLSearchParams()
    if (search.trim()) params.set('search', search.trim())
    if (roleFilter) params.set('role', roleFilter)
    return api(`/admin/users/?${params}`).then(setUsers)
  }, [search, roleFilter])
  useEffect(() => { api('/admin/departments/').then((d) => setDepartments(d.results ?? d)).catch(() => {}) }, [])
  useEffect(() => { load().catch(() => setUsers({ results: [], count: 0 })) }, [load])

  async function create(e) {
    e.preventDefault()
    setErrors({})
    setCreated('')
    const body = { email: form.email, full_name: form.full_name, role: form.role,
      department: form.department === '' ? null : Number(form.department) }
    if (form.password) body.password = form.password
    try {
      const user = await api('/admin/users/', { method: 'POST', body })
      setCreated(form.password ? `Account created for ${user.email}. Tell them the password you chose.`
        : `Account created. An invitation to set a password was emailed to ${user.email}.`)
      setForm({ email: '', full_name: '', role: form.role, department: '', password: '' })
      load()
    } catch (err) {
      setErrors(fieldErrors(err))
    }
  }

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const replace = (updated) => setUsers((u) => ({ ...u, results: u.results.map((x) => (x.id === updated.id ? updated : x)) }))
  return (
    <main className="sch-page">
      <p className="crumbs"><Link to="/dashboard">Dashboard</Link> / Manage</p>
      <h1>Users</h1>
      <ManageNav />

      <form className="decision-panel manage-form" onSubmit={create} aria-label="Add a staff account" noValidate>
        <h2>Add a staff account</h2>
        <p className="field-hint">Leave the password empty to email an invitation; the person then sets their own password.</p>
        <div className="manage-grid">
          <label>Email<input type="email" value={form.email} onChange={set('email')} required /></label>
          <label>Full name<input value={form.full_name} onChange={set('full_name')} required /></label>
          <label>Role
            <select value={form.role} onChange={set('role')}>
              {Object.entries(ROLE_LABELS).filter(([v]) => v !== 'student').map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label><span>Department{DEPARTMENT_ROLES.includes(form.role) && <span className="req"> * required</span>}</span>
            <select value={form.department} onChange={set('department')}>
              <option value="">None</option>
              {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </label>
          <label>Password (optional)<input type="password" autoComplete="new-password" value={form.password} onChange={set('password')} /></label>
        </div>
        {Object.entries(errors).map(([k, v]) => <p key={k} className="field-error" role="alert">{k === 'detail' ? v : `${k.replace('_', ' ')}: ${v}`}</p>)}
        {created && <p className="notice-ok" role="status">{created}</p>}
        <button type="submit">Add account</button>
      </form>

      <form className="filters" role="search" onSubmit={(e) => { e.preventDefault(); load() }}>
        <label>Search<input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name, email or Registration ID" /></label>
        <label>Role
          <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
            <option value="">All roles</option>
            {Object.entries(ROLE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
      </form>
      {!users ? <p>Loading...</p> : (
        <>
          <p role="status">{users.count} account{users.count === 1 ? '' : 's'}.</p>
          <div className="table-scroll">
            <table className="list-table">
              <thead><tr><th scope="col">Name</th><th scope="col">Role</th><th scope="col">Department</th><th scope="col">Access</th><th scope="col">Actions</th></tr></thead>
              <tbody>{users.results.map((u) => <UserRow key={u.id} user={u} departments={departments} onSaved={replace} />)}</tbody>
            </table>
          </div>
        </>
      )}
    </main>
  )
}
