import { useEffect } from 'react'
import './assets/styles/App.css'
import { AuthProvider } from './context/AuthContext'
import AppRoutes from './routes'

function App() {
  useEffect(() => {
    document.title = 'MentalCare Assistant'
  }, [])

  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}

export default App
