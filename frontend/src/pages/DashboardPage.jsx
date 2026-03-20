import { Link } from 'react-router-dom'

export default function DashboardPage({ user }) {
  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Welcome, {user.full_name}</h2>
          <p className="muted">Role: {user.role}</p>
        </div>
      </div>
      <div className="grid two">
        <div className="card">
          <h3>Project Modules</h3>
          <div className="stack-list">
            {user.role === 'student' ? (
              <>
                <Link className="primary-link" to="/simulator">Open AI Patient Simulator</Link>
                <Link className="primary-link" to="/decision">Open Scenario Trainer</Link>
              </>
            ) : (
              <Link className="primary-link" to="/faculty">Open Faculty Analytics Dashboard</Link>
            )}
          </div>
        </div>
        <div className="card">
          <h3>What this app can do</h3>
          <ul>
            <li>Assess therapeutic communication responses</li>
            <li>Train students using interactive scenarios</li>
            <li>Provide quick faculty insights</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
