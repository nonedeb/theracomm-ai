import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'

export default function LoginPage({ onLogin }) {
  const [isRegister, setIsRegister] = useState(false)
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    role: 'student',
    year_level: '4',
    section: 'A',
  })
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const endpoint = isRegister ? '/auth/register' : '/auth/login'
      const payload = isRegister ? form : { email: form.email, password: form.password }
      const { data } = await api.post(endpoint, payload)
      localStorage.setItem('token', data.token)
      localStorage.setItem('user', JSON.stringify(data.user))
      onLogin(data.user)
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.error || 'Request failed')
    }
  }

  return (
    <div className="auth-wrap">
      <div className="hero-card">
        <h1>TheraComm AI</h1>
        <p>Functional web app for therapeutic communication training, scenario practice, and faculty analytics.</p>
        <ul>
          <li>AI Patient Simulator</li>
          <li>Scenario-Based Decision Trainer</li>
          <li>Feedback and performance analytics</li>
        </ul>
      </div>
      <form className="auth-card" onSubmit={submit}>
        <h2>{isRegister ? 'Create account' : 'Login'}</h2>
        {isRegister && (
          <input placeholder="Full name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        )}
        <input placeholder="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <input placeholder="Password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        {isRegister && (
          <>
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              <option value="student">Student</option>
              <option value="faculty">Faculty</option>
            </select>
            {form.role === 'student' && (
              <div className="row">
                <input placeholder="Year level" value={form.year_level} onChange={(e) => setForm({ ...form, year_level: e.target.value })} />
                <input placeholder="Section" value={form.section} onChange={(e) => setForm({ ...form, section: e.target.value })} />
              </div>
            )}
          </>
        )}
        {error && <p className="error-text">{error}</p>}
        <button type="submit">{isRegister ? 'Register' : 'Login'}</button>
        <button type="button" className="secondary-btn" onClick={() => setIsRegister(!isRegister)}>
          {isRegister ? 'Have an account? Login' : 'Need an account? Register'}
        </button>
        <div className="demo-box">
          <strong>Demo credentials</strong>
          <p>Student: student@theracomm.ai / student123</p>
          <p>Faculty: faculty@theracomm.ai / faculty123</p>
        </div>
      </form>
    </div>
  )
}
