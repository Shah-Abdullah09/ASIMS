import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, openProtectedFile } from '../api.js'
import { useAuth } from '../AuthContext.jsx'
import { rupees } from '../scholarship/convert.js'
import { fileSize } from '../scholarship/files.js'
import * as O from '../scholarship/options.js'
import '../scholarship/scholarship.css'
import { completionText } from './format.js'
import { FileReview, FlagsPanel, InterviewForm, ReviewChip } from './panels.jsx'
import { PLACEMENT, QUEUES } from './roles.js'

const ROLE_TITLES = { father: 'Father', mother: 'Mother', guardian: 'Guardian' }
const day = (d) => (d ? new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—')
const when = (d) => new Date(d).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
const month = (d) => (d ? new Date(d).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' }) : '—')
const pick = (options, value) => options.find((o) => o.value === value)?.label || value || '—'
const yesNo = (v) => (v === true ? 'Yes' : v === false ? 'No' : '—')
const money = (v) => (v === null || v === undefined ? '—' : rupees(v))
const todayIso = () => new Date().toLocaleDateString('en-CA') // YYYY-MM-DD in local time

function Facts({ items }) {
  return (
    <dl className="facts">
      {items.map(([k, v]) => (
        <div key={k} className={typeof v === 'string' && v.length > 60 ? 'facts-wide' : undefined}>
          <dt>{k}</dt>
          <dd>{v === '' || v === null || v === undefined ? '—' : v}</dd>
        </div>
      ))}
    </dl>
  )
}

function Table({ caption, columns, rows, empty = 'None entered.' }) {
  if (!rows.length) return <p className="field-hint">{caption ? `${caption}: ` : ''}{empty}</p>
  return (
    <div className="table-scroll">
      <table className="list-table">
        {caption && <caption>{caption}</caption>}
        <thead><tr>{columns.map(([h]) => <th key={h} scope="col">{h}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => <tr key={i}>{columns.map(([h, f]) => <td key={h}>{f(r) ?? '—'}</td>)}</tr>)}
        </tbody>
      </table>
    </div>
  )
}

function Section({ id, title, children }) {
  return (
    <section className="review-section" aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      {children}
    </section>
  )
}

/** The actions the server says this user may take at the current stage, with remarks and percentage. */
function ActionPanel({ app, onSaved }) {
  const actions = app.available_actions
  const [chosen, setChosen] = useState(actions[0]?.action || '')
  const [remarks, setRemarks] = useState('')
  const [percentage, setPercentage] = useState(app.scholarship_percentage ?? '')
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState('')
  const current = actions.find((a) => a.action === chosen)

  async function save(e) {
    e.preventDefault()
    if (!current) return
    setSaving(true)
    setErrors({})
    setDone('')
    const body = { action: current.action, remarks }
    if (current.percentage && percentage !== '') body.percentage = Number(percentage)
    try {
      const updated = await api(`/scholarships/review/applications/${app.id}/actions/`, { method: 'POST', body })
      setRemarks('')
      setChosen(updated.available_actions[0]?.action || '')
      setDone(`Done: the case is now at "${O.STATUS_LABELS[updated.status]}".`)
      onSaved(updated)
    } catch (err) {
      setErrors(err.data && typeof err.data === 'object' ? err.data : { detail: err.message })
    } finally {
      setSaving(false)
    }
  }

  const err = (k) => errors[k] && [].concat(errors[k]).join(' ')
  return (
    <form className="decision-panel" onSubmit={save} noValidate aria-label="Decision">
      <h2>Decision</h2>
      <p>Current stage: <span className={`chip chip-${app.status}`}>{O.STATUS_LABELS[app.status]}</span></p>
      {app.scholarship_percentage != null && <p className="field-hint">Scholarship: {app.scholarship_percentage}% of the semester tuition fee</p>}
      {app.reviewed_at && <p className="field-hint">Last action {when(app.reviewed_at)} by {app.reviewed_by}</p>}
      {done && <p className="notice-ok" role="status">{done}</p>}
      {actions.length === 0 ? (
        <p className="field-hint">You have no action at this stage.</p>
      ) : (
        <>
          <div className="field">
            <label htmlFor="decision-action">Action</label>
            <select id="decision-action" value={chosen} onChange={(e) => setChosen(e.target.value)}>
              {actions.map((a) => <option key={a.action} value={a.action}>{a.label}</option>)}
            </select>
          </div>
          {current?.percentage && (
            <div className="field">
              <label htmlFor="decision-percentage">
                Scholarship percentage{current.percentage === 'required' && <span className="req"> * required</span>}
              </label>
              <input id="decision-percentage" type="number" min={1} max={100} step={1} value={percentage}
                onChange={(e) => setPercentage(e.target.value)} aria-invalid={err('percentage') ? true : undefined}
                aria-describedby="decision-percentage-msg" />
              {err('percentage') && <p className="field-error" id="decision-percentage-msg">{err('percentage')}</p>}
            </div>
          )}
          <div className="field">
            <label htmlFor="decision-remarks">Remarks{current?.remarks_required && <span className="req"> * required</span>}</label>
            <textarea id="decision-remarks" rows={3} maxLength={2000} value={remarks} onChange={(e) => setRemarks(e.target.value)}
              aria-invalid={err('remarks') ? true : undefined} aria-describedby="decision-remarks-msg"
              placeholder="Shown to the student" />
            {err('remarks') && <p className="field-error" id="decision-remarks-msg">{err('remarks')}</p>}
          </div>
          {current?.action === 'verify' && !app.completion.complete && (
            <p className="notice">Verifying needs a complete application: {completionText(app.completion).toLowerCase()}.</p>
          )}
          {errors.detail && <p className="field-error" role="alert">{err('detail')}</p>}
          {errors.action && (
            <div className="field-error" role="alert">
              {[].concat(errors.action).length > 1 ? (
                <>
                  <p>{[].concat(errors.action)[0]}</p>
                  <ul>{[].concat(errors.action).slice(1).map((m) => <li key={m}>{m}</li>)}</ul>
                </>
              ) : <p>{err('action')}</p>}
            </div>
          )}
          <button type="submit" disabled={saving}>{saving ? 'Saving...' : current?.label}</button>
        </>
      )}

      <h3>History</h3>
      <ol className="timeline">
        {app.status_history.map((h) => (
          <li key={`${h.changed_at}-${h.to_status}`}>
            <p><strong>{O.historyTitle(h)}</strong> <span className="field-hint">{h.changed_by}, {when(h.changed_at)} · now {O.STATUS_LABELS[h.to_status]}</span></p>
            {h.percentage != null && <p className="field-hint">Percentage: {h.percentage}%</p>}
            {h.remarks && <p>{h.remarks}</p>}
          </li>
        ))}
      </ol>
    </form>
  )
}

function DeclarationReview({ decl, canReceive, onChanged }) {
  const [date, setDate] = useState(todayIso())
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function call(method, body) {
    setBusy(true)
    setError('')
    try {
      await api(`/scholarships/declarations/${decl.id}/receive/`, { method, body })
      await onChanged()
    } catch (err) {
      const d = err.data
      setError(d?.received_on ? [].concat(d.received_on).join(' ') : err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <li className="doc-slot" aria-label={`Form 2: ${decl.person}`}>
      <div className="doc-head">
        <p className="card-title">{decl.person}: {decl.person_name || '—'}</p>
        <span className={`chip ${decl.is_complete ? 'chip-ok' : 'chip-warn'}`}>{decl.is_complete ? 'Complete' : 'Incomplete'}</span>
      </div>
      <p className="field-hint">Template: {decl.printable.title}</p>
      <ul className="checks">
        <li className={decl.scan ? 'done' : 'pending'}>
          {decl.scan ? (
            <>Scan: {decl.scan.original_name} ({fileSize(decl.scan.size)}){' '}
              <button type="button" className="link-button neutral"
                onClick={() => openProtectedFile(decl.scan.download_url).catch((e) => setError(e.message))}>View</button></>
          ) : 'Scan not uploaded yet'}
        </li>
        <li className={decl.physical_received_on ? 'done' : 'pending'}>
          {decl.physical_received_on
            ? `Original received on ${day(decl.physical_received_on)} by ${decl.physical_received_by}`
            : 'Original not received'}
        </li>
      </ul>
      {!canReceive ? null : decl.physical_received_on ? (
        <button type="button" className="secondary" disabled={busy}
          onClick={() => window.confirm('Undo "original received"?') && call('DELETE')}>
          Undo received
        </button>
      ) : (
        <div className="doc-upload">
          <label className="inline-field">
            Received on
            <input type="date" value={date} max={todayIso()} onChange={(e) => setDate(e.target.value)} />
          </label>
          <button type="button" disabled={busy || !date} onClick={() => call('POST', { received_on: date })}>
            Mark original received
          </button>
        </div>
      )}
      {error && <p className="field-error" role="alert">{error}</p>}
    </li>
  )
}

const NAV = [['personal', 'Personal'], ['family', 'Family'], ['parents', 'Parents'], ['income', 'Income'],
  ['accommodation', 'Accommodation'], ['expenditure', 'Expenditure'], ['assets', 'Assets'], ['education', 'Education'],
  ['documents', 'Documents'], ['form2', 'Form 2']]

/** Everything one applicant submitted, plus the actions open to the current user at this stage. */
export default function ReviewDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const [app, setApp] = useState(null)
  const [moved, setMoved] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(
    () => api(`/scholarships/review/applications/${id}/`).then(setApp)
      .catch((e) => setError(e.status === 404 ? 'Application not found (drafts are not shown).' : e.message)),
    [id],
  )
  useEffect(() => { load() }, [load])

  if (moved) {
    return (
      <main className="sch-page">
        <p className="notice-ok" role="status">
          Done. Application {moved.id} is now at "{O.STATUS_LABELS[moved.status]}" and has left your queue.
        </p>
        <Link className="button" to="/review">Back to {QUEUES[user.role]?.title || 'the list'}</Link>
      </main>
    )
  }
  if (error) return <main className="sch-page"><p className="field-error">{error}</p><Link to="/review">Back to the list</Link></main>
  if (!app) return <main className="sch-page"><p>Loading...</p></main>

  const s = app.summary
  const missingDocs = app.documents.filter((d) => d.missing)
  const parent = (role) => app.parents.find((p) => p.role === role)
  const isPlacement = PLACEMENT.includes(user.role)
  const verifying = isPlacement && app.status === 'placement_verification'
  const canReceive = isPlacement && ['placement_verification', 'returned'].includes(app.status)
  const interviewing = user.role === 'dac_member' && app.status === 'dac_review'
  const onActed = (updated) => (updated.left_queue ? setMoved(updated) : setApp(updated))

  return (
    <main className="sch-page">
      <p className="crumbs"><Link to="/review">{QUEUES[user.role]?.title || 'Scholarship applications'}</Link> / Application {app.id}</p>
      <h1>{app.applicant_name}</h1>
      <p className="status-line">
        <span className={`chip chip-${app.status}`}>{O.STATUS_LABELS[app.status]}</span>{' '}
        <span className="field-hint">
          Application {app.id} · {app.cycle.name} · {app.student.department || '—'} · submitted {day(app.submitted_at)} ·{' '}
          {completionText(app.completion)}
        </span>
      </p>
      <nav className="jump" aria-label="Sections">
        {NAV.map(([key, label]) => <a key={key} href={`#${key}`}>{label}</a>)}
      </nav>

      <div className="review-layout">
        <div className="review-main">
          {(verifying || app.flags?.length > 0) && (
            <Section id="corrections" title="Corrections requested">
              <FlagsPanel app={app} canEdit={verifying} onChanged={load} />
            </Section>
          )}
          {app.interview_date && (
            <Section id="interview" title="DAC interview">
              <Facts items={[
                ['Interview date', day(app.interview_date)], ['Recorded by', app.interview_recorded_by],
                ['Remarks', app.interview_remarks],
                ['Recommended scholarship', app.scholarship_percentage != null ? `${app.scholarship_percentage}% of the semester tuition fee` : '—'],
              ]} />
            </Section>
          )}
          <Section id="personal" title="Personal details">
            <Facts items={[
              ['Name', app.applicant_name], ['Registration ID', app.registration_id], ['Program', app.program],
              ['Department', app.student.department], ['Gender', pick(O.GENDER, app.gender)],
              ['Marital status', pick(O.MARITAL, app.marital_status)], ['CNIC', app.cnic],
              ['Date of birth', app.date_of_birth ? `${day(app.date_of_birth)} (age ${app.age})` : '—'],
              ['Domicile', app.domicile], ['Mobile', app.mobile], ['Telephone', app.tel_residence],
              ['Email', app.email || app.student.email], ['Present address', app.present_address],
              ['Permanent address', app.permanent_address],
            ]} />
          </Section>

          <Section id="family" title="Family">
            <Facts items={[['Family members living together', app.total_family_members]]} />
            <Table caption="Living with the applicant (Q9)" rows={app.household_members} columns={[
              ['Name', (r) => r.name], ['Relationship', (r) => pick(O.RELATIONSHIP, r.relationship)],
              ['Marital status', (r) => pick(O.MARITAL, r.marital_status)], ['Remarks', (r) => r.remarks],
            ]} />
            <Table caption="Studying (Q11)" rows={app.studying_members} columns={[
              ['Name', (r) => r.name], ['Relation', (r) => pick(O.RELATIONSHIP, r.relation)],
              ['Institute', (r) => r.institute], ['Fee per month', (r) => money(r.fee_per_month)],
            ]} />
            <Facts items={[['Total fees (11.1)', money(s.total_studying_fees)]]} />
          </Section>

          <Section id="parents" title="Parents & guardian">
            {['father', 'mother', 'guardian'].map((role) => {
              const p = parent(role)
              if (!p) return role === 'guardian' ? null : <p key={role} className="field-hint">No {role} details entered.</p>
              return (
                <div key={role} className="person">
                  <h3>{ROLE_TITLES[role]}</h3>
                  <Facts items={[
                    ['Name', p.name], ['CNIC', p.cnic], ...(role === 'guardian' ? [['Relationship', p.relationship_to_applicant]] : []),
                    ['Status', pick(O.LIFE_STATUS, p.status)], ['Professional status', pick(O.PROFESSION, p.profession)],
                    ['Employer / business', p.employer], ['Occupation type', p.occupation_type],
                    ['Designation & grade', p.designation_grade], ['NTN', p.ntn], ['Office telephone', p.tel_office],
                    ['Mobile', p.mobile], ['Gross monthly income', money(p.gross_monthly_income)],
                    ['Net monthly income', money(p.net_monthly_income)],
                  ]} />
                </div>
              )
            })}
          </Section>

          <Section id="income" title="Income">
            <Table caption="Family members earning (Q10)" rows={app.earning_members} columns={[
              ['Name', (r) => r.name], ['Relationship', (r) => pick(O.RELATIONSHIP, r.relationship)],
              ['Occupation', (r) => r.occupation], ['Organization', (r) => r.organization], ['Designation', (r) => r.designation],
              ['Gross', (r) => money(r.gross_pay)], ['Net', (r) => money(r.net_pay)], ['Remarks', (r) => r.remarks],
            ]} />
            <Facts items={[
              ["Applicant's gross pay", money(app.applicant_gross_income)], ["Applicant's net pay", money(app.applicant_net_income)],
              ['"Other" asset income from', app.asset_income_other_specify],
            ]} />
            <Table caption="Asset income per month (Q24)" rows={app.asset_income} columns={[
              ['Source', (r) => pick(O.ASSET_INCOME_SOURCES, r.source)], ['Father', (r) => money(r.father)],
              ['Mother', (r) => money(r.mother)], ['Spouse', (r) => money(r.spouse)], ['Self', (r) => money(r.self_amount)],
              ['Other', (r) => money(r.other)],
            ]} />
          </Section>

          <Section id="accommodation" title="Accommodation">
            <Facts items={[
              ['Type', pick(O.ACCOMMODATION_TYPE, app.accommodation_type)],
              ['Status', pick(O.ACCOMMODATION_STATUS, app.accommodation_status)],
              ['Rent paid by', pick(O.RENT_PAID_BY, app.rent_paid_by)], ['Monthly rent', money(app.monthly_rent)],
              ['Plot size (sq. ft.)', app.plot_size_sqft], ['Covered area (sq. ft.)', app.covered_area_sqft],
              ['Bedrooms', pick(O.BEDROOMS, app.bedrooms)], ['Air conditioners', pick(O.AIR_CONDITIONERS, app.air_conditioners)],
              ['Address', app.accommodation_address], ['Other house owned', yesNo(app.other_house_owned)],
              ['Other house details', app.other_house_details],
            ]} />
          </Section>

          <Section id="expenditure" title="Expenditure and disposable income">
            <Table caption="Utility bills, last three months (Q27)" rows={app.utility_months} columns={[
              ['Month', (r) => ['Most recent', 'Previous', 'Before that'][r.month_index - 1]],
              ['Telephone', (r) => money(r.telephone)], ['Electricity', (r) => money(r.electricity)],
              ['Gas', (r) => money(r.gas)], ['Water', (r) => money(r.water)],
            ]} />
            <table className="calc">
              <tbody>
                <tr><th scope="row">Net (take-home) pay of all earners</th><td>{rupees(s.monthly_net_pay)}</td></tr>
                <tr><th scope="row">+ Asset income (24.1)</th><td>{rupees(s.monthly_asset_income)}</td></tr>
                <tr className="calc-total"><th scope="row">= Total monthly income (25.1)</th><td>{rupees(s.total_monthly_income)}</td></tr>
                <tr><th scope="row">Education</th><td>{rupees(s.expenditure.education)}</td></tr>
                <tr><th scope="row">Accommodation</th><td>{rupees(s.expenditure.accommodation)}</td></tr>
                <tr><th scope="row">Utilities (average)</th><td>{rupees(s.expenditure.utilities)}</td></tr>
                <tr><th scope="row">Medical</th><td>{rupees(s.expenditure.medical)}</td></tr>
                <tr><th scope="row">Miscellaneous</th><td>{rupees(s.expenditure.misc)}</td></tr>
                <tr className="calc-total"><th scope="row">= Total monthly expenditure (29.1)</th><td>{rupees(s.total_monthly_expenditure)}</td></tr>
                <tr className="calc-total"><th scope="row">Net monthly disposable income (30)</th><td>{rupees(s.net_monthly_disposable)}</td></tr>
                <tr><th scope="row">Net annual disposable income (31)</th><td>{rupees(s.net_annual_disposable)}</td></tr>
              </tbody>
            </table>
            {app.negative_income_explanation && (
              <Facts items={[['Explanation of the income gap', app.negative_income_explanation]]} />
            )}
          </Section>

          <Section id="assets" title="Assets & financing">
            <Facts items={[['Owns transport', yesNo(app.owns_transport)], ['Cattle', app.cattle_count != null ? `${app.cattle_count} ${app.cattle_kind}`.trim() : '—']]} />
            {app.owns_transport && (
              <Table caption="Vehicles (Q32)" rows={app.vehicles} columns={[
                ['Type', (r) => (r.transport_type === 'other' ? r.transport_type_other : pick(O.TRANSPORT, r.transport_type))],
                ['Make / model', (r) => r.make_model], ['Engine (CC)', (r) => r.engine_cc],
                ['Registration', (r) => r.registration_no], ['Owned for', (r) => r.ownership_period],
              ]} />
            )}
            <Table caption="Land and plots (Q34)" rows={app.land_holdings} empty="None." columns={[
              ['Kind', (r) => pick(O.LAND_CATEGORIES, r.category)], ['Qty', (r) => r.quantity], ['Size', (r) => r.size],
              ['Location', (r) => r.location], ['Cultivable', (r) => r.cultivable_area], ['Yield / acre', (r) => r.yield_per_acre],
            ]} />
            <Table caption="Assets worth (Q35)" rows={app.asset_worth} columns={[
              ['Asset', (r) => pick(O.ASSET_TITLES, r.title)], ['Father', (r) => money(r.father)], ['Mother', (r) => money(r.mother)],
              ['Spouse', (r) => money(r.spouse)], ['Self', (r) => money(r.self_amount)], ['Guardian', (r) => money(r.guardian)],
            ]} />
            <Facts items={[
              ['Total assets worth (35.1)', money(s.asset_worth.total)], ['Education loan', yesNo(app.education_loan)],
              ['Loan details', app.education_loan_details], ['Other financing', app.other_financing],
              ['How admission was paid', app.admission_fee_paid_how],
            ]} />
          </Section>

          <Section id="education" title="Education and statement of purpose">
            <Table caption="Educational record (Q39)" rows={app.education_records} columns={[
              ['Level', (r) => pick(O.EDUCATION_LEVELS, r.level)], ['Institute', (r) => r.institute],
              ['Fee / month', (r) => money(r.monthly_fee)], ['From', (r) => month(r.from_month)], ['To', (r) => month(r.to_month)],
              ['Result', (r) => [r.division && `${r.division} division`, r.percentage && `${r.percentage}%`, r.cgpa && `CGPA ${r.cgpa}`].filter(Boolean).join(', ')],
            ]} />
            <Facts items={[['Last institution fee / month', money(app.last_institution_monthly_fee)], ['Other scholarships', yesNo(app.other_scholarships)]]} />
            {app.other_scholarships && (
              <Table caption="Previous scholarships" rows={app.previous_scholarships} columns={[
                ['Institute', (r) => r.institute], ['Scholarship', (r) => r.scholarship_name], ['Amount', (r) => money(r.total_amount)],
                ['Period', (r) => r.period], ['Level', (r) => r.level],
              ]} />
            )}
            <h3>Statement of purpose</h3>
            <p className="prose">{app.statement_of_purpose || '—'}</p>
            <Facts items={[['Undertaking accepted', yesNo(app.undertaking_accepted)], ['Typed name', app.undertaking_name], ['Date', day(app.undertaking_date)]]} />
          </Section>

          <Section id="documents" title="Documents">
            <p className={missingDocs.length ? 'notice' : 'notice-ok'}>
              {missingDocs.length ? `${missingDocs.length} required document(s) missing.` : 'All required documents uploaded.'}
            </p>
            <ul className="doc-list">
              {app.documents.filter((d) => d.files.length || d.required).map((d) => (
                <li key={d.slot} className={`doc-slot${d.missing ? ' doc-missing' : ''}`} aria-label={d.label}>
                  <div className="doc-head">
                    <p className="card-title">{d.label}</p>
                    {d.missing ? <span className="chip chip-warn">Missing</span> : <span className="field-hint">{d.files.length} file(s)</span>}
                  </div>
                  <ul className="doc-files">
                    {d.files.map((f) => (
                      <li key={f.id}>
                        <span className="doc-name">{f.original_name}</span>
                        <span className="field-hint">{fileSize(f.size)} · {day(f.uploaded_at)}</span>
                        <ReviewChip file={f} />
                        <span className="doc-actions">
                          <button type="button" className="link-button neutral" onClick={() => openProtectedFile(f.download_url)}>
                            View
                          </button>
                        </span>
                        {f.review_note && <p className="field-hint file-note">Note: {f.review_note}</p>}
                        {verifying && <FileReview appId={app.id} file={f} onChanged={load} />}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </Section>

          <Section id="form2" title="Form 2: stamp-paper income declarations">
            {app.declarations.length === 0 ? <p>No declaration needed (no earning parent or guardian).</p> : (
              <ul className="doc-list">
                {app.declarations.map((d) => <DeclarationReview key={d.id} decl={d} canReceive={canReceive} onChanged={load} />)}
              </ul>
            )}
          </Section>
        </div>

        <aside className="review-side">
          {interviewing && <InterviewForm app={app} onSaved={setApp} />}
          <ActionPanel app={app} onSaved={onActed} />
        </aside>
      </div>
    </main>
  )
}
