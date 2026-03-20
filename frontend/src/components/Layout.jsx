import { Link, useNavigate } from 'react-router-dom'

export default function Layout({ user, children }) {
  const navigate = useNavigate()

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    navigate('/')
    window.location.reload()
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <h1>TheraComm AI</h1>
          <p className="muted">Therapeutic communication training</p>
        </div>
        {user && (
          <nav>
            <Link to="/dashboard">Dashboard</Link>
            {user.role === 'student' && <Link to="/simulator">AI Patient Simulator</Link>}
            {user.role === 'student' && <Link to="/decision">Scenario Trainer</Link>}
            {user.role === 'faculty' && <Link to="/faculty">Faculty Analytics</Link>}
          </nav>
        )}
        <button className="secondary-btn" onClick={handleLogout}>Logout</button>
      </aside>
      <main className="content">{children}</main>
    </div>
  )
}
