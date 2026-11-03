import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext.jsx'
import { QUEUES, REPORT_ROLES } from '../review/roles.js'
import { ROLE_LABELS } from '../roles.js'

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
      ) : QUEUES[user.role] ? (
        <p>
          <Link to="/review">My work: {QUEUES[user.role].title}</Link>. {QUEUES[user.role].hint}
        </p>
      ) : (
        <p>Your role-specific tools will appear here as each module is built.</p>
      )}
      {REPORT_ROLES.includes(user.role) && (
        <p><Link to="/reports">Scholarship reports</Link>: figures by stage and department{user.role === 'placement_officer' || user.role === 'administrator' ? ', CSV download' : ''}.</p>
      )}
      {user.role === 'administrator' && (
        <p><Link to="/manage/users">Manage</Link>: staff accounts, departments, scholarship cycles and the audit log.</p>
      )}
      <p><Link to="/account/password">Change password</Link></p>
      <button onClick={onLogout}>Log out</button>
    </main>
  )
}
