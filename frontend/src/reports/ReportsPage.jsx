import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, downloadProtectedFile } from '../api.js'
import { useAuth } from '../AuthContext.jsx'
import { rupees } from '../scholarship/convert.js'
import '../scholarship/scholarship.css'

const CAN_EXPORT = ['placement_officer', 'administrator']

/** Scholarship figures for one cycle or all: headline numbers, then counts by stage and by department. */
export default function ReportsPage() {
  const { user } = useAuth()
  const [cycles, setCycles] = useState([])
  const [cycle, setCycle] = useState('')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => { api('/scholarships/cycles/').then(setCycles).catch(() => setCycles([])) }, [])
  useEffect(() => {
    api(`/reports/scholarships/${cycle ? `?cycle=${cycle}` : ''}`).then(setData).catch((e) => setError(e.message))
  }, [cycle])

  async function exportCsv() {
    setError('')
    const name = cycles.find((c) => String(c.id) === cycle)?.name || 'all'
    try {
      await downloadProtectedFile(`/reports/scholarships.csv${cycle ? `?cycle=${cycle}` : ''}`, `asims-scholarships-${name}.csv`)
    } catch (err) {
      setError(err.message)
    }
  }

  const tiles = data && [
    ['Submitted', data.submitted], ['In progress', data.in_progress], ['Approved', data.approved],
    ['Rejected', data.rejected], ['Completed', data.completed], ['Average approved', `${data.average_percentage}%`],
    ['Scholarship amount adjusted', rupees(data.total_scholarship_amount)],
  ]
  return (
    <main className="sch-page">
      <p className="crumbs"><Link to="/dashboard">Dashboard</Link></p>
      <h1>Scholarship reports</h1>
      <div className="filters">
        <label>Cycle
          <select value={cycle} onChange={(e) => setCycle(e.target.value)}>
            <option value="">All cycles</option>
            {cycles.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        {CAN_EXPORT.includes(user.role) && <button type="button" onClick={exportCsv}>Download CSV (Excel)</button>}
      </div>
      {error && <p className="field-error" role="alert">{error}</p>}
      {!data ? <p>Loading...</p> : (
        <>
          <ul className="stat-tiles" aria-label="Headline figures">
            {tiles.map(([label, value]) => (
              <li key={label} className="stat-tile"><span className="stat-value">{value}</span><span className="stat-label">{label}</span></li>
            ))}
          </ul>
          <p className="field-hint">Drafts are not counted. Approved includes completed cases.</p>
          <div className="report-tables">
            <section aria-labelledby="by-stage">
              <h2 id="by-stage">By stage</h2>
              <table className="list-table">
                <thead><tr><th scope="col">Stage</th><th scope="col" className="num">Applications</th></tr></thead>
                <tbody>{data.by_stage.map((r) => <tr key={r.stage}><td>{r.label}</td><td className="num">{r.count}</td></tr>)}</tbody>
              </table>
            </section>
            <section aria-labelledby="by-department">
              <h2 id="by-department">By department</h2>
              {data.by_department.length === 0 ? <p>No applications yet.</p> : (
                <table className="list-table">
                  <thead><tr><th scope="col">Department</th><th scope="col" className="num">Submitted</th><th scope="col" className="num">Approved</th><th scope="col" className="num">Rejected</th></tr></thead>
                  <tbody>
                    {data.by_department.map((r) => (
                      <tr key={r.department}><td>{r.department}</td><td className="num">{r.submitted}</td><td className="num">{r.approved}</td><td className="num">{r.rejected}</td></tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
          </div>
        </>
      )}
    </main>
  )
}
