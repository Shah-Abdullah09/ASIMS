import { useEffect, useState } from 'react'

function App() {
  const [apiStatus, setApiStatus] = useState('checking')

  useEffect(() => {
    fetch('/api/v1/health/')
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error('bad response'))))
      .then((data) => setApiStatus(data.status))
      .catch(() => setApiStatus('unreachable'))
  }, [])

  return (
    <main>
      <h1>ASIMS</h1>
      <p>Automated Scholarship and Internship Management System</p>
      <p>API status: {apiStatus}</p>
    </main>
  )
}

export default App
