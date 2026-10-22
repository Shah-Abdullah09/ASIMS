import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, apiUpload, openProtectedFile } from '../api.js'
import { LockedBanner, StepNav } from './ApplicationWizard.jsx'
import { ACCEPT, checkFile, fileSize, MAX_MB, uploadError } from './files.js'
import { useApplication } from './useApplication.js'

const KIND = {
  always: 'Required',
  conditional: 'Required for you',
  optional: 'Optional',
}

/** Hidden file input behind a normal button. */
export function FilePicker({ label, onPick, disabled, ariaLabel }) {
  const input = useRef(null)
  return (
    <>
      <button type="button" className="secondary" disabled={disabled} aria-label={ariaLabel}
        onClick={() => input.current.click()}>
        {label}
      </button>
      <input ref={input} type="file" accept={ACCEPT} hidden data-testid={ariaLabel}
        onChange={(e) => {
          const file = e.target.files[0]
          e.target.value = '' // allow choosing the same file again
          if (file) onPick(file)
        }} />
    </>
  )
}

function Slot({ entry, editable, appId, onChanged }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const required = entry.required
  const kind = entry.kind === 'conditional' && !required ? 'Not required for you' : KIND[entry.kind]
  const full = entry.files.length >= entry.max_files

  async function run(action) {
    setBusy(true)
    setError('')
    try {
      await action()
      await onChanged()
    } catch (err) {
      setError(uploadError(err))
    } finally {
      setBusy(false)
    }
  }

  function upload(file) {
    const problem = checkFile(file)
    if (problem) return setError(problem)
    const data = new FormData()
    data.append('slot', entry.slot)
    data.append('file', file)
    return run(() => apiUpload(`/scholarships/applications/${appId}/documents/`, data))
  }

  function replace(doc, file) {
    const problem = checkFile(file)
    if (problem) return setError(problem)
    const data = new FormData()
    data.append('file', file)
    return run(() => apiUpload(`/scholarships/applications/${appId}/documents/${doc.id}/`, data, { method: 'PUT' }))
  }

  function remove(doc) {
    if (!window.confirm(`Delete ${doc.original_name}?`)) return
    return run(() => api(`/scholarships/applications/${appId}/documents/${doc.id}/`, { method: 'DELETE' }))
  }

  return (
    <li className={`doc-slot${entry.missing ? ' doc-missing' : ''}`} aria-label={entry.label}>
      <div className="doc-head">
        <p className="card-title">{entry.label}</p>
        <span className={`chip ${required ? (entry.missing ? 'chip-warn' : 'chip-ok') : ''}`}>
          {entry.missing ? `${kind} · missing` : required ? `${kind} · uploaded` : kind}
        </span>
      </div>
      <p className="field-hint">{entry.reason}</p>
      {entry.files.length > 0 && (
        <ul className="doc-files">
          {entry.files.map((doc) => (
            <li key={doc.id}>
              <span className="doc-name">{doc.original_name}</span>
              <span className="field-hint">{fileSize(doc.size)} · {new Date(doc.uploaded_at).toLocaleDateString('en-GB')}</span>
              <span className="doc-actions">
                <button type="button" className="link-button neutral" onClick={() => openProtectedFile(doc.download_url).catch((e) => setError(e.message))}>
                  View
                </button>
                {editable && (
                  <>
                    <FilePicker label="Replace" ariaLabel={`Replace ${doc.original_name}`} disabled={busy} onPick={(f) => replace(doc, f)} />
                    <button type="button" className="link-button" disabled={busy} onClick={() => remove(doc)}>Delete</button>
                  </>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      {error && <p className="field-error" role="alert">{error}</p>}
      {editable && (
        <div className="doc-upload">
          <FilePicker label={busy ? 'Uploading...' : entry.files.length ? 'Add another file' : 'Upload file'}
            ariaLabel={`Upload to ${entry.label}`} disabled={busy || full} onPick={upload} />
          <span className="field-hint">
            {full ? `Maximum of ${entry.max_files} files reached.` : `PDF, JPG or PNG, up to ${MAX_MB} MB. Up to ${entry.max_files} files.`}
          </span>
        </div>
      )}
    </li>
  )
}

export default function DocumentsPage() {
  const { id } = useParams()
  const { app, readiness, refreshReadiness, loadError } = useApplication(id)
  const [checklist, setChecklist] = useState(null)
  const [error, setError] = useState('')
  const [onlyMissing, setOnlyMissing] = useState(false)

  const load = useCallback(
    () => api(`/scholarships/applications/${id}/documents/`).then(setChecklist).catch((e) => setError(e.message)),
    [id],
  )
  useEffect(() => { load() }, [load])

  if (loadError || error) return <main className="sch-page"><p className="field-error">{loadError || error}</p></main>
  if (!app || !checklist) return <main className="sch-page"><p>Loading...</p></main>

  const editable = app.is_editable
  const missing = checklist.filter((e) => e.missing).length
  const shown = onlyMissing ? checklist.filter((e) => e.missing) : checklist
  const changed = async () => {
    await load()
    refreshReadiness()
  }

  return (
    <main className="sch-page">
      <p className="crumbs"><Link to="/scholarships">My scholarship applications</Link> / {app.cycle.name} / Application {app.id}</p>
      <h1>Need Based Financial Grant</h1>
      <LockedBanner app={app} />
      <div className="wizard">
        <StepNav id={id} current="documents" readiness={readiness} editable={editable} />
        <section className="step-body">
          <h2>Supporting documents</h2>
          <p>
            Upload a clear scan or photo of each document. Which documents are required depends on your answers: for
            example a rent agreement is required only if your house is rented.
          </p>
          <p className={missing ? 'notice' : 'notice-ok'} role="status">
            {missing ? `${missing} required document${missing > 1 ? 's' : ''} still missing.` : 'All required documents are uploaded.'}
          </p>
          <label className="checkbox">
            <input type="checkbox" checked={onlyMissing} onChange={(e) => setOnlyMissing(e.target.checked)} />
            Show only missing documents
          </label>
          <p className="field-hint">The income declaration (checklist item 5) is Form 2, on the next step.</p>
          <ul className="doc-list">
            {shown.map((entry) => <Slot key={entry.slot} entry={entry} editable={editable} appId={id} onChanged={changed} />)}
          </ul>
          <div className="actions">
            <Link className="button secondary" to={`/scholarships/${id}/undertaking`}>Back</Link>
            <Link className="button" to={`/scholarships/${id}/form2`}>Continue to Form 2</Link>
          </div>
        </section>
      </div>
    </main>
  )
}
