import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api.js'
import { LockedBanner, StepNav, useApplication } from './ApplicationWizard.jsx'
import { rupees } from './convert.js'
import { DOCUMENT_LABELS } from './options.js'
import { stepByKey } from './steps.jsx'

function describe(errors) {
  // readiness errors: {field: [msg]} or, for parents, {father: {field: [msg]} | [msg]}
  return Object.entries(errors).flatMap(([field, value]) => {
    if (Array.isArray(value)) return value.map((m) => (m === 'This field is required.' ? `${label(field)} is required.` : m))
    return Object.entries(value).map(([f, msgs]) => `${label(field)}: ${label(f)} - ${[].concat(msgs).join(' ')}`)
  })
}

const label = (key) => key.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())

export default function ApplicationReview() {
  const { id } = useParams()
  const { app, setApp, readiness, refreshReadiness, loadError } = useApplication(id)
  const [confirming, setConfirming] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState({ kind: '', text: '' })

  if (loadError) return <main className="sch-page"><p className="field-error">{loadError}</p></main>
  if (!app) return <main className="sch-page"><p>Loading...</p></main>

  const s = app.summary
  const editable = app.is_editable
  const ready = readiness?.ready

  async function submit() {
    setSubmitting(true)
    setMessage({ kind: '', text: '' })
    try {
      setApp(await api(`/scholarships/applications/${id}/submit/`, { method: 'POST' }))
      setMessage({ kind: 'ok', text: 'Your application has been submitted. A confirmation email has been sent to you.' })
    } catch (err) {
      setMessage({ kind: 'error', text: err.message })
      refreshReadiness()
    } finally {
      setSubmitting(false)
      setConfirming(false)
    }
  }

  return (
    <main className="sch-page">
      <p className="crumbs"><Link to="/scholarships">My scholarship applications</Link> / {app.cycle.name} / Application {app.id}</p>
      <h1>Need Based Financial Grant</h1>
      <LockedBanner app={app} />
      <div className="wizard">
        <StepNav id={id} current="review" readiness={readiness} editable={editable} />
        <section className="step-body">
          <h2>Review & submit</h2>
          {message.text && (
            <p className={message.kind === 'ok' ? 'notice-ok' : 'field-error'} role={message.kind === 'ok' ? 'status' : 'alert'}>
              {message.text}
            </p>
          )}

          <h3>How your disposable income is calculated</h3>
          <table className="calc">
            <tbody>
              <tr><th scope="row">Net (take-home) pay of all earners</th><td>{rupees(s.monthly_net_pay)}</td></tr>
              <tr><th scope="row">+ Monthly income from assets (24.1)</th><td>{rupees(s.monthly_asset_income)}</td></tr>
              <tr className="calc-total"><th scope="row">= Total monthly income (25.1)</th><td>{rupees(s.total_monthly_income)}</td></tr>
              <tr><th scope="row">Education (fees of family members studying)</th><td>{rupees(s.expenditure.education)}</td></tr>
              <tr><th scope="row">+ Accommodation (rent)</th><td>{rupees(s.expenditure.accommodation)}</td></tr>
              <tr><th scope="row">+ Utilities (monthly average)</th><td>{rupees(s.expenditure.utilities)}</td></tr>
              <tr><th scope="row">+ Medical</th><td>{rupees(s.expenditure.medical)}</td></tr>
              <tr><th scope="row">+ Miscellaneous</th><td>{rupees(s.expenditure.misc)}</td></tr>
              <tr className="calc-total"><th scope="row">= Total monthly expenditure (29.1)</th><td>{rupees(s.total_monthly_expenditure)}</td></tr>
              <tr className="calc-total"><th scope="row">Net monthly disposable income (30) = 25.1 - 29.1</th><td>{rupees(s.net_monthly_disposable)}</td></tr>
              <tr><th scope="row">Net annual disposable income (31) = 30 x 12</th><td>{rupees(s.net_annual_disposable)}</td></tr>
              <tr><th scope="row">Total annual income (25.2) = 25.1 x 12</th><td>{rupees(s.total_annual_income)}</td></tr>
              <tr><th scope="row">Total assets worth (35.1)</th><td>{rupees(s.asset_worth.total)}</td></tr>
            </tbody>
          </table>

          {editable && readiness && !ready && (
            <>
              <h3>Still needed before you can submit</h3>
              {Object.entries(readiness.sections).map(([key, errors]) => (
                <div key={key} className="todo">
                  <p>
                    <strong>{stepByKey[key]?.title || label(key)}</strong>{' '}
                    <Link to={`/scholarships/${id}/${key}?check=1`}>Fix</Link>
                  </p>
                  <ul>{describe(errors).map((m) => <li key={m}>{m}</li>)}</ul>
                </div>
              ))}
              {readiness.missing_documents.length > 0 && (
                <div className="todo">
                  <p><strong>Documents</strong></p>
                  <ul>{readiness.missing_documents.map((slot) => <li key={slot}>{DOCUMENT_LABELS[slot] || slot}</li>)}</ul>
                </div>
              )}
              {readiness.problems.map((p) => <p key={p} className="field-error">{p}</p>)}
            </>
          )}

          {editable && (
            <div className="actions">
              {!confirming ? (
                <button type="button" disabled={!ready || submitting} onClick={() => setConfirming(true)}>Submit application</button>
              ) : (
                <div className="confirm" role="group" aria-label="Confirm submission">
                  <p>After submitting you cannot change your answers or documents. Submit now?</p>
                  <button type="button" disabled={submitting} onClick={submit}>{submitting ? 'Submitting...' : 'Yes, submit'}</button>
                  <button type="button" className="secondary" onClick={() => setConfirming(false)}>Cancel</button>
                </div>
              )}
              {!ready && readiness && <p className="field-hint">Complete everything above to enable submission.</p>}
            </div>
          )}
        </section>
      </div>
    </main>
  )
}
