import { useState } from 'react'
import { api, apiUpload, openProtectedFile } from '../api.js'
import { rupees } from '../scholarship/convert.js'
import { ACCEPT } from '../scholarship/files.js'
import { scholarshipAmount } from './format.js'

const day = (d) => (d ? new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—')
const todayIso = () => new Date().toLocaleDateString('en-CA')
const fieldError = (err, key) => (err?.data?.[key] ? [].concat(err.data[key]).join(' ') : '')

/** The award letter for staff: download the letter (signed scan if uploaded) or the generated PDF; Placement
records the date the signed letter was issued and may upload its scan. */
export function AwardLetterPanel({ app, canSign, onSaved }) {
  const letter = app.award_letter
  const [date, setDate] = useState(letter.signed_issued_on || todayIso())
  const [file, setFile] = useState(null)
  const [error, setError] = useState('')
  const [done, setDone] = useState('')
  const [busy, setBusy] = useState(false)

  async function save(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    setDone('')
    const data = new FormData()
    data.append('signed_issued_on', date)
    if (file) data.append('file', file)
    try {
      const updated = await apiUpload(`/scholarships/review/applications/${app.id}/award-letter/signed/`, data)
      setFile(null)
      setDone('Saved.')
      onSaved(updated)
    } catch (err) {
      setError(fieldError(err, 'signed_issued_on') || fieldError(err, 'file') || err.message)
    } finally {
      setBusy(false)
    }
  }

  const open = (url) => openProtectedFile(url).catch((e) => setError(e.message))
  return (
    <div className="award-letter">
      <dl className="facts">
        <div><dt>Reference</dt><dd>{letter.reference}</dd></div>
        <div><dt>Issued</dt><dd>{day(letter.issued_on)}</dd></div>
        <div><dt>Scholarship</dt><dd>{letter.percentage}% of the semester tuition fee</dd></div>
        <div><dt>Signed letter issued</dt><dd>{letter.signed_issued_on ? day(letter.signed_issued_on) : 'Not yet'}</dd></div>
      </dl>
      <div className="actions">
        <button type="button" className="secondary" onClick={() => open(letter.generated_url)}>Open generated letter</button>
        {letter.signed_copy && (
          <button type="button" className="secondary" onClick={() => open(letter.download_url)}>Open signed scan</button>
        )}
      </div>
      {canSign && (
        <form className="signed-form" onSubmit={save} aria-label="Signed award letter">
          <label>
            Signed letter issued on
            <input type="date" value={date} max={todayIso()} onChange={(e) => setDate(e.target.value)} required />
          </label>
          <label>
            Scan of the signed letter (optional{letter.signed_copy ? ', replaces the current one' : ''})
            <input type="file" accept={ACCEPT} onChange={(e) => setFile(e.target.files[0] || null)} />
          </label>
          <button type="submit" disabled={busy}>{busy ? 'Saving...' : 'Record signed letter'}</button>
        </form>
      )}
      {done && <p className="notice-ok" role="status">{done}</p>}
      {error && <p className="field-error" role="alert">{error}</p>}
    </div>
  )
}

/** The recorded fee adjustment, for staff and the student. */
export function FeeAdjustmentFacts({ adj }) {
  return (
    <dl className="facts">
      <div><dt>Semester tuition fee</dt><dd>{rupees(adj.semester_fee)}</dd></div>
      <div><dt>Scholarship ({adj.percentage}%)</dt><dd>{rupees(adj.scholarship_amount)}</dd></div>
      <div><dt>Fee payable after adjustment</dt><dd>{rupees(adj.fee_payable)}</dd></div>
      <div><dt>Fee voucher / challan</dt><dd>{adj.voucher_number}</dd></div>
      <div><dt>Adjusted on</dt><dd>{day(adj.adjusted_on)}</dd></div>
      <div><dt>Recorded by</dt><dd>{adj.recorded_by}</dd></div>
      {adj.remarks && <div className="facts-wide"><dt>Remarks</dt><dd>{adj.remarks}</dd></div>}
    </dl>
  )
}

/** Finance enters the semester fee and voucher; the amounts are previewed and then calculated by the server. */
export function FinancePanel({ app, onSaved }) {
  const [fee, setFee] = useState('')
  const [voucher, setVoucher] = useState('')
  const [date, setDate] = useState(todayIso())
  const [remarks, setRemarks] = useState('')
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const pct = app.scholarship_percentage
  const feeNumber = Number(fee)
  const valid = Number.isInteger(feeNumber) && feeNumber > 0
  const amount = valid ? scholarshipAmount(feeNumber, pct) : null

  async function save(e) {
    e.preventDefault()
    setBusy(true)
    setErrors({})
    try {
      const updated = await api(`/scholarships/review/applications/${app.id}/fee-adjustment/`, {
        method: 'POST', body: { semester_fee: feeNumber, voucher_number: voucher, adjusted_on: date, remarks },
      })
      onSaved(updated)
    } catch (err) {
      setErrors({ fee: fieldError(err, 'semester_fee'), voucher: fieldError(err, 'voucher_number'),
        date: fieldError(err, 'adjusted_on'), detail: err.data?.detail || (err.status >= 500 ? err.message : '') })
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="decision-panel" onSubmit={save} noValidate aria-label="Fee adjustment">
      <h2>Fee adjustment</h2>
      <p className="field-hint">Approved scholarship: {pct}% of the semester tuition fee. Recording the adjustment completes the case.</p>
      <div className="field">
        <label htmlFor="fee">Semester tuition fee (Rs)</label>
        <input id="fee" type="number" min={1} step={1} value={fee} onChange={(e) => setFee(e.target.value)}
          aria-invalid={errors.fee ? true : undefined} />
        {errors.fee && <p className="field-error">{errors.fee}</p>}
      </div>
      {amount !== null && (
        <table className="calc" aria-label="Calculated amounts">
          <tbody>
            <tr><th scope="row">Scholarship ({pct}%)</th><td>{rupees(amount)}</td></tr>
            <tr className="calc-total"><th scope="row">Fee payable after adjustment</th><td>{rupees(feeNumber - amount)}</td></tr>
          </tbody>
        </table>
      )}
      <div className="field">
        <label htmlFor="voucher">Fee voucher / challan number</label>
        <input id="voucher" value={voucher} maxLength={40} onChange={(e) => setVoucher(e.target.value)}
          aria-invalid={errors.voucher ? true : undefined} />
        {errors.voucher && <p className="field-error">{errors.voucher}</p>}
      </div>
      <div className="field">
        <label htmlFor="adjusted-on">Adjusted on</label>
        <input id="adjusted-on" type="date" value={date} max={todayIso()} onChange={(e) => setDate(e.target.value)}
          aria-invalid={errors.date ? true : undefined} />
        {errors.date && <p className="field-error">{errors.date}</p>}
      </div>
      <div className="field">
        <label htmlFor="fee-remarks">Remarks (optional)</label>
        <textarea id="fee-remarks" rows={2} maxLength={2000} value={remarks} onChange={(e) => setRemarks(e.target.value)} />
      </div>
      {errors.detail && <p className="field-error" role="alert">{errors.detail}</p>}
      <button type="submit" disabled={busy || !valid}>{busy ? 'Saving...' : 'Record fee adjustment'}</button>
    </form>
  )
}
