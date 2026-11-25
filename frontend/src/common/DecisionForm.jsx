import { useState } from 'react'

const messages = (v) => [].concat(v)

/** The actions the server offers this user at the current stage: pick one, add remarks and take it.
 * `submit(body)` sends the action and returns the updated case. A chain adds its own inputs with
 * `fields(current, error)` and their values with `extend(current)`; `notice(current)` warns before an action.
 * `header` is shown above the actions and `children` (e.g. the history) below them. */
export default function DecisionForm({ actions, stages, submit, onSaved, fields, extend, notice, header, children,
  emptyText = 'You have no action at this stage.' }) {
  const [chosen, setChosen] = useState(actions[0]?.action || '')
  const [remarks, setRemarks] = useState('')
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
    try {
      const updated = await submit({ action: current.action, remarks, ...extend?.(current) })
      setRemarks('')
      setChosen(updated.available_actions[0]?.action || '')
      setDone(`Done: the case is now at "${stages[updated.status]}".`)
      onSaved(updated)
    } catch (err) {
      setErrors(err.data && typeof err.data === 'object' ? err.data : { detail: err.message })
    } finally {
      setSaving(false)
    }
  }

  const error = (k) => errors[k] && messages(errors[k]).join(' ')
  return (
    <form className="decision-panel" onSubmit={save} noValidate aria-label="Decision">
      {header}
      {done && <p className="notice-ok" role="status">{done}</p>}
      {actions.length === 0 ? (
        <p className="field-hint">{emptyText}</p>
      ) : (
        <>
          <div className="field">
            <label htmlFor="decision-action">Action</label>
            <select id="decision-action" value={chosen} onChange={(e) => setChosen(e.target.value)}>
              {actions.map((a) => <option key={a.action} value={a.action}>{a.label}</option>)}
            </select>
          </div>
          {current && fields?.(current, error)}
          <div className="field">
            <label htmlFor="decision-remarks">Remarks{current?.remarks_required && <span className="req"> * required</span>}</label>
            <textarea id="decision-remarks" rows={3} maxLength={2000} value={remarks} onChange={(e) => setRemarks(e.target.value)}
              aria-invalid={error('remarks') ? true : undefined} aria-describedby="decision-remarks-msg"
              placeholder="Shown to the student" />
            {error('remarks') && <p className="field-error" id="decision-remarks-msg">{error('remarks')}</p>}
          </div>
          {current && notice?.(current)}
          {errors.detail && <p className="field-error" role="alert">{error('detail')}</p>}
          {errors.action && (
            <div className="field-error" role="alert">
              {messages(errors.action).length > 1 ? (
                <>
                  <p>{messages(errors.action)[0]}</p>
                  <ul>{messages(errors.action).slice(1).map((m) => <li key={m}>{m}</li>)}</ul>
                </>
              ) : <p>{error('action')}</p>}
            </div>
          )}
          <button type="submit" disabled={saving}>{saving ? 'Saving...' : current?.label}</button>
        </>
      )}
      {children}
    </form>
  )
}
