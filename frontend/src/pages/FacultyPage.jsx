import { useEffect, useState } from 'react'
import api from '../services/api'

export default function FacultyPage() {
  const [data, setData] = useState(null)

  useEffect(() => {
    api.get('/faculty/analytics').then(({ data }) => setData(data))
  }, [])

  if (!data) return <p>Loading analytics...</p>

  return (
    <div>
      <div className="page-header">
        <h2>Faculty Analytics Dashboard</h2>
      </div>
      <div className="grid four">
        <div className="card stat-card"><h3>{data.summary.students_count}</h3><p>Students</p></div>
        <div className="card stat-card"><h3>{data.summary.average_chat_score}</h3><p>Average Chat Score</p></div>
        <div className="card stat-card"><h3>{data.summary.average_decision_score}</h3><p>Average Decision Score</p></div>
        <div className="card stat-card"><h3>{data.summary.students_needing_support}</h3><p>Need Support</p></div>
      </div>
      <div className="grid two">
        <div className="card">
          <h3>Common weak skill</h3>
          <p>{data.summary.common_weak_skill}</p>
        </div>
        <div className="card">
          <h3>Recent Sessions</h3>
          <ul>
            {data.recent_sessions.map((session) => (
              <li key={session.session_id}>Session #{session.session_id} — Score: {session.overall_score ?? 'Pending'} — {session.status}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
