import { NavLink } from 'react-router-dom'
import '../scholarship/scholarship.css'

const PAGES = [['/manage/users', 'Users'], ['/manage/departments', 'Departments'], ['/manage/cycles', 'Scholarship cycles'],
  ['/manage/audit', 'Audit log']]

/** The Administrator's Manage area: one page per kind of record. */
export default function ManageNav() {
  return (
    <nav className="jump manage-nav" aria-label="Manage">
      {PAGES.map(([to, label]) => (
        <NavLink key={to} to={to} className={({ isActive }) => (isActive ? 'active' : undefined)}>{label}</NavLink>
      ))}
    </nav>
  )
}
