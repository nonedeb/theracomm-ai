import { Navigate, Route, Routes } from 'react-router-dom'
import { useMemo, useState } from 'react'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import SimulatorPage from './pages/SimulatorPage'
import DecisionTrainerPage from './pages/DecisionTrainerPage'
import FacultyPage from './pages/FacultyPage'
import Layout from './components/Layout'

function ProtectedRoute({ user, children, role }) {
  if (!user) return <Navigate to="/" replace />
  if (role && user.role !== role) return <Navigate to="/dashboard" replace />
  return children
}

export default function App() {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('user')
    return saved ? JSON.parse(saved) : null
  })

  const layoutWrapped = (component) => <Layout user={user}>{component}</Layout>

  const routes = useMemo(() => (
    <Routes>
      <Route path="/" element={user ? <Navigate to="/dashboard" replace /> : <LoginPage onLogin={setUser} />} />
      <Route path="/dashboard" element={<ProtectedRoute user={user}>{layoutWrapped(<DashboardPage user={user} />)}</ProtectedRoute>} />
      <Route path="/simulator" element={<ProtectedRoute user={user} role="student">{layoutWrapped(<SimulatorPage />)}</ProtectedRoute>} />
      <Route path="/decision" element={<ProtectedRoute user={user} role="student">{layoutWrapped(<DecisionTrainerPage />)}</ProtectedRoute>} />
      <Route path="/faculty" element={<ProtectedRoute user={user} role="faculty">{layoutWrapped(<FacultyPage />)}</ProtectedRoute>} />
    </Routes>
  ), [user])

  return routes
}
