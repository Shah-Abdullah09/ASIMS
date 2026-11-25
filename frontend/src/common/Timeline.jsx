import { when } from './dates.js'

/** A case's history, oldest first: what happened, (who did it,) when, the stage it moved to and the remarks.
 * `title(h)` names the step, `stages` maps a stage to its label and `detail(h)` adds a chain's own line. */
export default function Timeline({ history, title, stages, showWho = false, detail }) {
  return (
    <ol className="timeline">
      {history.map((h) => (
        <li key={`${h.changed_at}-${h.to_status}`}>
          <p><strong>{title(h)}</strong> <span className="field-hint">{showWho && `${h.changed_by}, `}{when(h.changed_at)} · now {stages[h.to_status]}</span></p>
          {detail?.(h)}
          {h.remarks && <p>{h.remarks}</p>}
        </li>
      ))}
    </ol>
  )
}
