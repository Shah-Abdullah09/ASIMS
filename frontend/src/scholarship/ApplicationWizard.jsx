import { useState } from 'react'
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api.js'
import { STATUS_LABELS } from './options.js'
import { STEPS, stepByKey } from './steps.jsx'
import { useApplication } from './useApplication.js'
import './scholarship.css'

/** Left-hand list of steps; marks steps that still need something before submitting. */
export function StepNav({ id, current, readiness, editable, onNavigate }) {
  const items = [
    ...STEPS.map((s) => ({ key: s.key, title: s.title })),
    { key: 'documents', title: 'Documents' },
    { key: 'form2', title: 'Form 2 declarations' },
    { key: 'review', title: 'Review & submit' },
  ]
  return (
    <nav className="step-nav" aria-label="Application steps">
      <ol>
        {items.map((s, i) => {
          const needs = editable && (s.key === 'documents' ? readiness?.missing_documents?.length > 0
            : readiness?.sections?.[s.key])
          return (
            <li key={s.key} className={s.key === current ? 'current' : undefined}>
              <Link to={`/scholarships/${id}/${s.key}`} aria-current={s.key === current ? 'step' : undefined}
                onClick={(e) => onNavigate && !onNavigate() && e.preventDefault()}>
                <span className="step-num">{i + 1}</span> {s.title}
                {needs && <span className="badge-warn" title="Something is still needed here">needs attention</span>}
              </Link>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

export function LockedBanner({ app }) {
  if (app.is_editable) return null
  return (
    <p className="notice">
      Submitted on {new Date(app.submitted_at).toLocaleDateString('en-GB')}. Status: <strong>{STATUS_LABELS[app.status]}</strong>.
      The application can no longer be changed.
    </p>
  )
}

export default function ApplicationWizard() {
  const { id, step } = useParams()
  const [search] = useSearchParams()
  const navigate = useNavigate()
  const { app, setApp, readiness, refreshReadiness, loadError } = useApplication(id)
  const def = stepByKey[step]
  const [form, setForm] = useState(null)
  const [errors, setErrors] = useState({})
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState({ kind: '', text: '' })
  const [loadedFor, setLoadedFor] = useState(null)
  const [shownStep, setShownStep] = useState(step)

  // (Re)fill the form when the step changes or the server returns newly saved data
  const formKey = app && def ? `${def.key}:${app.updated_at}` : null
  if (step !== shownStep) {
    setShownStep(step)
    setErrors({})
    setMessage({ kind: '', text: '' })
  }
  if (formKey && formKey !== loadedFor) {
    setLoadedFor(formKey)
    setForm(def.fromApp(app))
    setDirty(false)
    return null // re-renders straight away with the new step's form
  }

  if (!def) return <Navigate to={`/scholarships/${id}/personal`} replace />
  if (loadError) return <main className="sch-page"><p className="field-error">{loadError}</p><Link to="/scholarships">Back</Link></main>
  if (!app || !form) return <main className="sch-page"><p>Loading...</p></main>

  const index = STEPS.indexOf(def)
  const editable = app.is_editable
  const set = (name, value) => {
    setForm((f) => ({ ...f, [name]: value }))
    setDirty(true)
  }
  const confirmLeave = () => !dirty || window.confirm('You have unsaved changes on this step. Leave without saving?')
  // After "Fix" on the review page (?check=1), show what is still required beside each field
  const shownErrors = Object.keys(errors).length ? errors
    : (search.get('check') === '1' && readiness?.sections?.[step]) || {}

  async function save(nextPath) {
    setSaving(true)
    setMessage({ kind: '', text: '' })
    const { payload, remap } = def.toPayload(form)
    try {
      const updated = await api(`/scholarships/applications/${id}/sections/${def.key}/`, { method: 'PATCH', body: payload })
      setErrors({})
      setApp(updated)
      refreshReadiness()
      if (nextPath) navigate(nextPath)
      else setMessage({ kind: 'ok', text: 'Saved as draft.' })
    } catch (err) {
      if (err.status === 400 && err.data) {
        setErrors(remap(err.data))
        setMessage({ kind: 'error', text: 'Nothing was saved. Please correct the fields marked in red.' })
      } else {
        setMessage({ kind: 'error', text: err.message })
      }
    } finally {
      setSaving(false)
    }
  }

  const next = index < STEPS.length - 1 ? `/scholarships/${id}/${STEPS[index + 1].key}` : `/scholarships/${id}/documents`
  const prev = index > 0 ? `/scholarships/${id}/${STEPS[index - 1].key}` : null

  return (
    <main className="sch-page">
      <p className="crumbs"><Link to="/scholarships">My scholarship applications</Link> / {app.cycle.name} / Application {app.id}</p>
      <h1>Need Based Financial Grant</h1>
      <LockedBanner app={app} />
      <div className="wizard">
        <StepNav id={id} current={step} readiness={readiness} editable={editable} onNavigate={confirmLeave} />
        <form className="step-body" noValidate onSubmit={(e) => { e.preventDefault(); save(next) }}>
          <h2>Step {index + 1}: {def.title}</h2>
          {message.text && (
            <p className={message.kind === 'ok' ? 'notice-ok' : 'field-error'} role={message.kind === 'ok' ? 'status' : 'alert'}>
              {message.text}
            </p>
          )}
          <def.Fields form={form} set={set} errors={shownErrors} app={app} disabled={!editable} />
          <div className="actions">
            {prev && <Link className="button secondary" to={prev} onClick={(e) => !confirmLeave() && e.preventDefault()}>Back</Link>}
            {editable ? (
              <>
                <button type="button" className="secondary" disabled={saving} onClick={() => save(null)}>Save draft</button>
                <button type="submit" disabled={saving}>{saving ? 'Saving...' : 'Save and continue'}</button>
              </>
            ) : (
              <Link className="button" to={next}>Next</Link>
            )}
          </div>
        </form>
      </div>
    </main>
  )
}
