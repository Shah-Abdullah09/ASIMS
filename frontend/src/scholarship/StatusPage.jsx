import { Link, useParams } from 'react-router-dom'
import { useApplication } from './useApplication.js'
import { STATUS_LABELS } from './options.js'
import './scholarship.css'

const when = (d) => new Date(d).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })

/** Where the student's application stands: the three completion checks, the decision and the timeline. */
export default function StatusPage() {
  const { id } = useParams()
  const { app, loadError } = useApplication(id)

  if (loadError) return <main className="sch-page"><p className="field-error">{loadError}</p></main>
  if (!app) return <main className="sch-page"><p>Loading...</p></main>

  const c = app.completion
  const needsForm2 = c.declarations_required > 0
  const checks = [
    { done: c.form_submitted, text: 'Application form submitted', todo: <Link to={`/scholarships/${id}/review`}>Review and submit</Link> },
    {
      done: !needsForm2 || c.scans_uploaded,
      text: needsForm2 ? `Form 2 scan${c.declarations_required > 1 ? 's' : ''} uploaded` : 'Form 2 not needed for your family',
      todo: <Link to={`/scholarships/${id}/form2`}>Upload on the Form 2 page</Link>,
    },
    {
      done: !needsForm2 || c.physical_copies_received,
      text: needsForm2 ? 'Original stamp paper received by the Placement Office' : null,
      todo: 'Hand the original to the Placement Office',
    },
  ].filter((x) => x.text)

  const decided = app.status === 'approved' || app.status === 'rejected'

  return (
    <main className="sch-page">
      <p className="crumbs"><Link to="/scholarships">My scholarship applications</Link> / {app.cycle.name} / Application {app.id}</p>
      <h1>Application status</h1>
      <p className="status-line">
        <span className={`chip chip-${app.status}`}>{STATUS_LABELS[app.status]}</span>
        {app.submitted_at && <span className="field-hint"> Submitted {when(app.submitted_at)}</span>}
      </p>
      {app.review_remarks && (
        <div className={decided ? 'decision' : 'notice'}>
          <p><strong>Remarks from the Placement Office</strong></p>
          <p>{app.review_remarks}</p>
        </div>
      )}

      <h2>Is my application complete?</h2>
      <p className={c.complete ? 'notice-ok' : 'field-hint'}>
        {c.complete ? 'Yes. Everything needed has been received.' : 'Not yet. Complete the items still pending below.'}
      </p>
      <ul className="checks">
        {checks.map((x) => (
          <li key={x.text} className={x.done ? 'done' : 'pending'}>
            <span>{x.text}</span>
            {!x.done && <span className="field-hint"> · {x.todo}</span>}
          </li>
        ))}
      </ul>

      <h2>Timeline</h2>
      {app.status_history.length === 0 ? <p>Nothing has happened yet. Your application is still a draft.</p> : (
        <ol className="timeline">
          {app.status_history.map((h) => (
            <li key={h.changed_at}>
              <p><strong>{STATUS_LABELS[h.to_status]}</strong> <span className="field-hint">{when(h.changed_at)}, {h.changed_by_role}</span></p>
              {h.remarks && <p>{h.remarks}</p>}
            </li>
          ))}
        </ol>
      )}

      <div className="actions">
        <Link className="button secondary" to={`/scholarships/${id}/personal`}>View my answers</Link>
        <Link className="button secondary" to={`/scholarships/${id}/documents`}>Documents</Link>
        <Link className="button" to={`/scholarships/${id}/form2`}>Form 2</Link>
      </div>
    </main>
  )
}
