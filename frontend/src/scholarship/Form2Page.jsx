import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, apiUpload, openProtectedFile } from '../api.js'
import { LockedBanner, StepNav } from './ApplicationWizard.jsx'
import { useApplication } from './useApplication.js'
import { FilePicker } from './DocumentsPage.jsx'
import { checkFile, fileSize, MAX_MB, uploadError } from './files.js'

const date = (d) => new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

/** The official declaration text exactly as returned by the server (university wording, values filled in). */
function Sheet({ printable }) {
  return (
    <article className="sheet" aria-label={`Declaration text: ${printable.title}`}>
      <p className="sheet-title">{printable.title}</p>
      <p className="sheet-note"><em>Note:</em> {printable.note}</p>
      <p>{printable.header}</p>
      {printable.items.map((item) => <p key={item}>{item}</p>)}
      <p>{printable.closing}</p>
      <p className="sheet-sign">{printable.signature_line}</p>
      <p className="sheet-counter">COUNTERSIGNED</p>
      <div className="sheet-counter-grid">
        {printable.countersigned_by.map((c) => (
          <div key={c.title}>
            {c.fields.map((f) => <p key={f}>{f}: ____________________</p>)}
            <p>({c.title})</p>
          </div>
        ))}
      </div>
    </article>
  )
}

function Declaration({ decl, appId, onChanged, printing, onPrint }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const p = decl.printable
  const ref = p.student_reference

  async function upload(file) {
    const problem = checkFile(file)
    if (problem) return setError(problem)
    setBusy(true)
    setError('')
    const data = new FormData()
    data.append('file', file)
    try {
      await apiUpload(`/scholarships/applications/${appId}/declarations/${decl.id}/scan/`, data)
      await onChanged()
    } catch (err) {
      setError(uploadError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className={`declaration${printing ? ' print-target' : ''}`} aria-labelledby={`decl-${decl.id}`}>
      <h3 id={`decl-${decl.id}`}>{decl.person}: {decl.person_name || 'name not entered yet'}</h3>
      <p className="no-print field-hint">Template: {p.title}</p>

      {/* Shown on the printout but kept outside the official wording */}
      <dl className="reference">
        <div><dt>Student</dt><dd>{ref.student_name || '—'}</dd></div>
        <div><dt>Registration ID</dt><dd>{ref.registration_id || '—'}</dd></div>
        <div><dt>Application no.</dt><dd>{ref.application_no}</dd></div>
      </dl>

      <Sheet printable={p} />

      <div className="no-print">
        <button type="button" className="secondary" onClick={onPrint}>Print this declaration</button>
        <h4>What to do</h4>
        <ol className="steps-list">{p.instructions.map((i) => <li key={i}>{i}</li>)}</ol>

        <h4>Scan of the signed stamp paper</h4>
        <ul className="checks">
          <li className={decl.scan ? 'done' : 'pending'}>
            {decl.scan
              ? <>Scan uploaded: {decl.scan.original_name} ({fileSize(decl.scan.size)}, {date(decl.scan.uploaded_at)}){' '}
                  <button type="button" className="link-button neutral"
                    onClick={() => openProtectedFile(decl.scan.download_url).catch((e) => setError(e.message))}>View</button></>
              : 'Scan not uploaded yet'}
          </li>
          <li className={decl.physical_received_on ? 'done' : 'pending'}>
            {decl.physical_received_on
              ? `Original received by the Placement Office on ${date(decl.physical_received_on)}${decl.physical_received_by ? ` (${decl.physical_received_by})` : ''}`
              : 'Original not yet received by the Placement Office'}
          </li>
        </ul>
        {error && <p className="field-error" role="alert">{error}</p>}
        {decl.can_upload_scan ? (
          <div className="doc-upload">
            <FilePicker label={busy ? 'Uploading...' : decl.scan ? 'Replace scan' : 'Upload scan'} disabled={busy}
              ariaLabel={`Upload scan for ${decl.person}`} onPick={upload} />
            <span className="field-hint">PDF, JPG or PNG, up to {MAX_MB} MB. You can upload it after submitting.</span>
          </div>
        ) : (
          decl.scan && <p className="field-hint">The office has the original, so the scan can no longer be changed.</p>
        )}
      </div>
    </section>
  )
}

export default function Form2Page() {
  const { id } = useParams()
  const { app, readiness, loadError } = useApplication(id)
  const [declarations, setDeclarations] = useState(null)
  const [error, setError] = useState('')
  const [printingId, setPrintingId] = useState(null)

  const load = useCallback(
    () => api(`/scholarships/applications/${id}/declarations/`).then(setDeclarations).catch((e) => setError(e.message)),
    [id],
  )
  useEffect(() => { load() }, [load])

  // Print only the chosen declaration, then go back to normal
  useEffect(() => {
    if (printingId === null) return undefined
    const done = () => setPrintingId(null)
    window.addEventListener('afterprint', done)
    window.print()
    return () => window.removeEventListener('afterprint', done)
  }, [printingId])

  if (loadError || error) return <main className="sch-page"><p className="field-error">{loadError || error}</p></main>
  if (!app || !declarations) return <main className="sch-page"><p>Loading...</p></main>

  return (
    <main className={`sch-page${printingId !== null ? ' printing' : ''}`}>
      <p className="crumbs no-print"><Link to="/scholarships">My scholarship applications</Link> / {app.cycle.name} / Application {app.id}</p>
      <h1 className="no-print">Need Based Financial Grant</h1>
      <div className="no-print"><LockedBanner app={app} /></div>
      <div className="wizard">
        <div className="no-print"><StepNav id={id} current="form2" readiness={readiness} editable={app.is_editable} /></div>
        <section className="step-body">
          <h2 className="no-print">Form 2: stamp-paper income declarations</h2>
          {declarations.length === 0 ? (
            <p className="notice">
              No declaration is needed: none of your parents or guardian is recorded as earning. If that is wrong,
              update the <Link to={`/scholarships/${id}/parents`}>Parents & guardian</Link> step.
            </p>
          ) : (
            <p className="no-print">
              Each earning parent or guardian declares their own income on stamp paper. The text below is the
              university's wording with the details you entered filled in; complete any blank lines by hand. Your
              application is complete only when the form is submitted, each scan is uploaded and the Placement Office
              has received each original.
            </p>
          )}
          {declarations.map((d) => (
            <Declaration key={d.id} decl={d} appId={id} onChanged={load} printing={printingId === d.id}
              onPrint={() => setPrintingId(d.id)} />
          ))}
          <div className="actions no-print">
            <Link className="button secondary" to={`/scholarships/${id}/documents`}>Back</Link>
            <Link className="button" to={`/scholarships/${id}/${app.is_editable ? 'review' : 'status'}`}>
              {app.is_editable ? 'Continue to review' : 'View status'}
            </Link>
          </div>
        </section>
      </div>
    </main>
  )
}
