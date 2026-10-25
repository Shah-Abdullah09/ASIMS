// Browser-side checks and labels for uploaded files (the server re-checks the real file content).
export const MAX_MB = 5
export const ACCEPT = '.pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png'
const ALLOWED_EXT = ['pdf', 'jpg', 'jpeg', 'png']

/** Quick check in the browser so obvious mistakes are caught before uploading; the server checks the real content. */
export function checkFile(file) {
  const ext = file.name.split('.').pop().toLowerCase()
  if (!ALLOWED_EXT.includes(ext)) return 'Only PDF, JPG or PNG files are accepted.'
  if (file.size > MAX_MB * 1024 * 1024) return `The file is ${(file.size / 1048576).toFixed(1)} MB. The limit is ${MAX_MB} MB.`
  if (file.size === 0) return 'The file is empty.'
  return null
}

export const fileSize = (bytes) => (bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`)

export function uploadError(err) {
  const file = err.data?.file
  return file ? [].concat(file).join(' ') : err.message
}
