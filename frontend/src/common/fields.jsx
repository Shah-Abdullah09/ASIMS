import { useId } from 'react'
import { fieldError } from './convert.js'

/** A labelled control with its hint and its error message underneath. */
export function Field({ label, error, hint, required, wide, children }) {
  const id = useId()
  const control = typeof children === 'function' ? children({ id, invalid: Boolean(error), describedBy: `${id}-msg` }) : children
  return (
    <div className={`field${wide ? ' field-wide' : ''}${error ? ' field-invalid' : ''}`}>
      <label htmlFor={id}>
        {label}
        {required && <span className="req" aria-hidden="true"> *</span>}
      </label>
      {control}
      {hint && !error && <p className="field-hint" id={`${id}-msg`}>{hint}</p>}
      {error && <p className="field-error" id={`${id}-msg`}>{error}</p>}
    </div>
  )
}

const controlProps = ({ id, invalid, describedBy }) => ({
  id,
  'aria-invalid': invalid || undefined,
  'aria-describedby': describedBy,
})

/** Text, number, date, month or email input bound to form[name]. */
export function Input({ form, set, errors, name, label, type = 'text', hint, required, wide, disabled, ...rest }) {
  return (
    <Field label={label} hint={hint} required={required} wide={wide} error={fieldError(errors, name)}>
      {(p) => (
        <input
          {...controlProps(p)}
          type={type === 'money' ? 'text' : type}
          inputMode={type === 'money' || type === 'number' ? 'numeric' : undefined}
          value={form[name]}
          onChange={(e) => set(name, e.target.value)}
          disabled={disabled}
          {...rest}
        />
      )}
    </Field>
  )
}

export function Select({ form, set, errors, name, label, options, hint, required, wide, disabled, placeholder = 'Select' }) {
  return (
    <Field label={label} hint={hint} required={required} wide={wide} error={fieldError(errors, name)}>
      {(p) => (
        <select {...controlProps(p)} value={form[name]} onChange={(e) => set(name, e.target.value)} disabled={disabled}>
          <option value="">{placeholder}</option>
          {options.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      )}
    </Field>
  )
}

/** Yes / No question stored as 'yes' | 'no' | '' in the form. */
export function YesNo(props) {
  return <Select {...props} options={[{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }]} />
}

export function TextArea({ form, set, errors, name, label, hint, required, disabled, maxLength, rows = 4 }) {
  const length = form[name]?.length ?? 0
  return (
    <Field label={label} required={required} wide error={fieldError(errors, name)}
      hint={maxLength ? `${hint ? `${hint} ` : ''}${length} / ${maxLength} characters` : hint}>
      {(p) => (
        <textarea {...controlProps(p)} rows={rows} value={form[name]} maxLength={maxLength}
          onChange={(e) => set(name, e.target.value)} disabled={disabled} />
      )}
    </Field>
  )
}

/** Read-only value shown in the same layout as an input. */
export function Display({ label, value, hint }) {
  return (
    <div className="field">
      <span className="field-label">{label}</span>
      <p className="field-display">{value || '—'}</p>
      {hint && <p className="field-hint">{hint}</p>}
    </div>
  )
}

/**
 * Editable table for the form's repeating rows.
 * columns: [{ name, label, type: 'text'|'money'|'number'|'select'|'month', options, width }]
 * fixedLabels: when given, rows are fixed (one per label, e.g. income sources) and cannot be added or removed.
 */
export function RowsTable({ caption, rows, setRows, columns, makeRow, errors, addLabel = 'Add row', max = 20,
  fixedLabels, rowHeader = 'Item', disabled }) {
  const { rows: rowErrors, list } = errors
  const update = (i, name, value) => setRows(rows.map((r, j) => (j === i ? { ...r, [name]: value } : r)))

  return (
    <div className="rows-table">
      {caption && <p className="rows-caption">{caption}</p>}
      {list && <p className="field-error">{list}</p>}
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {fixedLabels ? <th scope="col">{rowHeader}</th> : <th scope="col">#</th>}
              {columns.map((c) => <th key={c.name} scope="col" style={c.width ? { minWidth: c.width } : undefined}>{c.label}</th>)}
              {!fixedLabels && !disabled && <th scope="col"><span className="visually-hidden">Remove</span></th>}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={columns.length + 2} className="rows-empty">No rows yet.</td></tr>
            )}
            {rows.map((row, i) => {
              const errs = rowErrors[String(i)] || {}
              const rowLevel = errs.non_field_errors && [].concat(errs.non_field_errors).join(' ')
              const rowName = fixedLabels ? fixedLabels[i] : `Row ${i + 1}`
              return [
                <tr key={`r${i}`} className={Object.keys(errs).length ? 'row-invalid' : undefined}>
                  <th scope="row">{fixedLabels ? fixedLabels[i] : i + 1}</th>
                  {columns.map((c) => {
                    const err = fieldError(errs, c.name)
                    const cellLabel = `${rowName}: ${c.label}`
                    return (
                      <td key={c.name}>
                        {c.type === 'select' ? (
                          <select aria-label={cellLabel} aria-invalid={err ? true : undefined} value={row[c.name]}
                            onChange={(e) => update(i, c.name, e.target.value)} disabled={disabled}>
                            <option value="">Select</option>
                            {c.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                          </select>
                        ) : (
                          <input aria-label={cellLabel} aria-invalid={err ? true : undefined} value={row[c.name]}
                            type={c.type === 'month' ? 'month' : 'text'}
                            inputMode={c.type === 'money' || c.type === 'number' ? 'numeric' : undefined}
                            onChange={(e) => update(i, c.name, e.target.value)} disabled={disabled} />
                        )}
                        {err && <p className="field-error">{err}</p>}
                      </td>
                    )
                  })}
                  {!fixedLabels && !disabled && (
                    <td>
                      <button type="button" className="link-button" onClick={() => setRows(rows.filter((_, j) => j !== i))}
                        aria-label={`Remove ${rowName}`}>
                        Remove
                      </button>
                    </td>
                  )}
                </tr>,
                rowLevel && (
                  <tr key={`e${i}`}><td colSpan={columns.length + 2}><p className="field-error">{rowLevel}</p></td></tr>
                ),
              ]
            })}
          </tbody>
        </table>
      </div>
      {!fixedLabels && !disabled && rows.length < max && (
        <button type="button" className="secondary" onClick={() => setRows([...rows, makeRow()])}>{addLabel}</button>
      )}
    </div>
  )
}
