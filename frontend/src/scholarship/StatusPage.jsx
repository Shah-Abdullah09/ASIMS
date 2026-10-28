import { Link, useParams } from 'react-router-dom'
import { ReturnedBanner } from './ApplicationWizard.jsx'
import { historyTitle, STATUS_LABELS } from './options.js'
import { CHAIN, isReturned } from './returned.js'
import { useApplication } from './useApplication.js'
import './scholarship.css'

const when = (d) => new Date(d).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })

/** The stages of the approval chain: done, current, or still to come (or where a rejection stopped it). */
function StageProgress({ app }) {
  const rejected = app.status === 'rejected'
  // A returned case is still in Placement verification; a rejected one stopped where it was rejected
  const at = isReturned(app) ? 'placement_verification'
    : rejected ? [...app.status_history].reverse().find((h) => h.to_status === 'rejected')?.from_status : app.status
  const index = CHAIN.indexOf(at)
  return (
    <ol className="stage-progress" aria-label="Approval stages">
      {CHAIN.map((stage, i) => {
        const state = i < index ? 'done' : i === index ? (rejected ? 'stopped' : 'current') : 'todo'
        const note = { done: 'done', current: 'current stage', stopped: 'not approved here', todo: '' }[state]
        return (
          <li key={stage} className={`stage-${state}`} aria-current={state === 'current' ? 'step' : undefined}>
            {STATUS_LABELS[stage]}{note && <span className="field-hint"> ({note})</span>}
          </li>
        )
      })}
    </ol>
  )
}

/** Where the student's application stands: the exact stage, the completion checks, the decision and the timeline. */
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

  const approved = app.status === 'awaiting_fee_adjustment'
  const rejected = app.status === 'rejected'

  return (
    <main className="sch-page">
      <p className="crumbs"><Link to="/scholarships">My scholarship applications</Link> / {app.cycle.name} / Application {app.id}</p>
      <h1>Application status</h1>
      <p className="status-line">
        Current stage: <span className={`chip chip-${app.status}`}>{STATUS_LABELS[app.status]}</span>
        {app.submitted_at && <span className="field-hint"> Submitted {when(app.submitted_at)}</span>}
      </p>

      {isReturned(app) && <ReturnedBanner app={app} />}
      {approved && (
        <div className="decision" role="status">
          <p><strong>Approved by the Vice Chancellor.</strong></p>
          {app.scholarship_percentage != null && <p>Scholarship: {app.scholarship_percentage}% of the semester tuition fee.</p>}
          <p>The Finance Office will now adjust your fee.</p>
        </div>
      )}
      {rejected && app.review_remarks && (
        <div className="decision">
          <p><strong>Your application was not approved.</strong></p>
          <p>Reason: {app.review_remarks}</p>
        </div>
      )}

      {app.status !== 'draft' && (
        <>
          <h2>Progress</h2>
          <StageProgress app={app} />
        </>
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
            <li key={`${h.changed_at}-${h.to_status}`}>
              <p><strong>{historyTitle(h)}</strong> <span className="field-hint">{when(h.changed_at)} · now {STATUS_LABELS[h.to_status]}</span></p>
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
