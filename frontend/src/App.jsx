import { Link, Navigate, Route, Routes } from 'react-router-dom'
import logo from './assets/au-logo.png'
import { useAuth } from './AuthContext.jsx'
import NotificationBell from './notifications/NotificationBell.jsx'
import NotificationsPage from './notifications/NotificationsPage.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Login from './pages/Login.jsx'
import { ChangePassword, ForgotPassword, ResetPassword } from './pages/PasswordPages.jsx'
import Register from './pages/Register.jsx'
import VerifyEmail from './pages/VerifyEmail.jsx'
import ApplicationReview from './scholarship/ApplicationReview.jsx'
import ApplicationWizard from './scholarship/ApplicationWizard.jsx'
import DocumentsPage from './scholarship/DocumentsPage.jsx'
import Form2Page from './scholarship/Form2Page.jsx'
import ScholarshipHome from './scholarship/ScholarshipHome.jsx'
import StatusPage from './scholarship/StatusPage.jsx'
import ReviewDetail from './review/ReviewDetail.jsx'
import ReviewList from './review/ReviewList.jsx'
import { STAFF } from './review/roles.js'

/** Only signed-in users; with `role`, only that role (or one of a list of roles). */
function RequireAuth({ children, role }) {
  const { user, loading } = useAuth()
  if (loading) return <p>Loading...</p>
  if (!user) return <Navigate to="/login" replace />
  if (role && ![].concat(role).includes(user.role)) return <Navigate to="/dashboard" replace />
  return children
}

/** University logo and name on every page; the signed-in person's name on the right. */
function AppHeader() {
  const { user } = useAuth()
  return (
    <header className="app-header">
      <Link className="brand-link" to={user ? '/dashboard' : '/login'}>
        <img className="brand-logo" src={logo} alt="Air University" />
        <span>
          <span className="brand-name">ASIMS</span><br />
          <span className="brand-sub">Air University Multan · Scholarship and Internship Management</span>
        </span>
      </Link>
      {user && <span className="header-user">{user.full_name}</span>}
      {user && <NotificationBell />}
    </header>
  )
}

export default function App() {
  return (
    <>
      <AppHeader />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/account/password" element={<RequireAuth><ChangePassword /></RequireAuth>} />
        <Route path="/notifications" element={<RequireAuth><NotificationsPage /></RequireAuth>} />
        <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
        <Route path="/scholarships" element={<RequireAuth role="student"><ScholarshipHome /></RequireAuth>} />
        <Route path="/scholarships/:id/review" element={<RequireAuth role="student"><ApplicationReview /></RequireAuth>} />
        <Route path="/scholarships/:id/documents" element={<RequireAuth role="student"><DocumentsPage /></RequireAuth>} />
        <Route path="/scholarships/:id/form2" element={<RequireAuth role="student"><Form2Page /></RequireAuth>} />
        <Route path="/scholarships/:id/status" element={<RequireAuth role="student"><StatusPage /></RequireAuth>} />
        <Route path="/scholarships/:id/:step" element={<RequireAuth role="student"><ApplicationWizard /></RequireAuth>} />
        <Route path="/review" element={<RequireAuth role={STAFF}><ReviewList /></RequireAuth>} />
        <Route path="/review/:id" element={<RequireAuth role={STAFF}><ReviewDetail /></RequireAuth>} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </>
  )
}
