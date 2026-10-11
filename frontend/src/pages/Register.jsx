import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

export default function Register() {
  const [departments, setDepartments] = useState([])
  const [form, setForm] = useState({ full_name: '', email: '', password: '', department: '' })
  const [error, setError] = useState('')
  const [done, setDone] = useState('')

  useEffect(() => {
    api('/departments/', { auth: false }).then(setDepartments).catch(() => setDepartments([]))
  }, [])

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value })

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      const res = await api('/auth/register/', {
        method: 'POST',
        auth: false,
        body: { ...form, department: Number(form.department) },
      })
      setDone(res.detail)
    } catch (err) {
      setError(err.message)
    }
  }

  if (done) {
    return (
      <main>
        <h1>Check your email</h1>
        <p>{done}</p>
        <Link to="/login">Back to login</Link>
      </main>
    )
  }

  return (
    <main>
      <h1>Student Registration</h1>
      <form onSubmit={onSubmit}>
        <label>
          Full name
          <input value={form.full_name} onChange={set('full_name')} required />
        </label>
        <label>
          Email
          <input type="email" value={form.email} onChange={set('email')} required />
        </label>
        <label>
          Department
          <select value={form.department} onChange={set('department')} required>
            <option value="">Select department</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Password
          <input type="password" value={form.password} onChange={set('password')} required />
        </label>
        {error && <p role="alert">{error}</p>}
        <button type="submit">Register</button>
      </form>
      <p>
        Already registered? <Link to="/login">Log in</Link>
      </p>
    </main>
  )
}
