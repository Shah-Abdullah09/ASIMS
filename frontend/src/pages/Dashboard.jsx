import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext.jsx'

const ROLE_LABELS = {
  student: 'Student',
  placement_officer: 'Placement Officer',
  dac_member: 'DAC Member',
  dic: 'Departmental Internship Coordinator',
  faculty_supervisor: 'Faculty Supervisor',
  director: 'Director',
  registrar: 'Registrar',
  vice_chancellor: 'Vice Chancellor',
  finance_officer: 'Finance Officer',
  administrator: 'Administrator',
}

export default function Dashboard() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function onLogout() {
    logout()
    navigate('/login')
  }

  return (
    <main>
      <h1>Welcome, {user.full_name}</h1>
      <p>Role: {ROLE_LABELS[user.role] ?? user.role}</p>
      {user.department_name && <p>Department: {user.department_name}</p>}
      {user.role === 'student' ? (
        <p>
          <Link to="/scholarships">Scholarship applications</Link>: apply for the Need Based Financial Grant or
          continue your application.
        </p>
      ) : ['placement_officer', 'administrator'].includes(user.role) ? (
        <p>
          <Link to="/review">Review scholarship applications</Link>: submitted Need Based Financial Grant
          applications, documents, Form 2 and decisions.
        </p>
      ) : (
        <p>Your role-specific tools will appear here as each module is built.</p>
      )}
      <button onClick={onLogout}>Log out</button>
    </main>
  )
}
