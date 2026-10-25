import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'

/** Loads one of the student's applications and its readiness check. */
export function useApplication(id) {
  const [app, setApp] = useState(null)
  const [readiness, setReadiness] = useState(null)
  const [loadError, setLoadError] = useState('')

  const refreshReadiness = useCallback(
    () => api(`/scholarships/applications/${id}/readiness/`).then(setReadiness).catch(() => setReadiness(null)),
    [id],
  )

  useEffect(() => {
    api(`/scholarships/applications/${id}/`)
      .then((data) => {
        setApp(data)
        if (data.is_editable) refreshReadiness()
      })
      .catch((err) => setLoadError(err.status === 404 ? 'Application not found.' : err.message))
  }, [id, refreshReadiness])

  return { app, setApp, readiness, refreshReadiness, loadError }
}
