import { useEffect, useState } from 'react'
import api from '../services/api'

export default function SimulatorPage() {
  const [scenarios, setScenarios] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [session, setSession] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [evaluation, setEvaluation] = useState(null)

  useEffect(() => {
    api.get('/scenarios?type=chat').then(({ data }) => {
      setScenarios(data.scenarios)
      if (data.scenarios[0]) setSelectedId(String(data.scenarios[0].id))
    })
  }, [])

  const startSession = async () => {
    const { data } = await api.post('/chat/start', { scenario_id: Number(selectedId) })
    setSession(data)
    setMessages(data.messages)
    setEvaluation(null)
  }

  const sendMessage = async () => {
    if (!input.trim() || !session) return
    const { data } = await api.post(`/chat/${session.session_id}/message`, { message: input })
    setMessages((prev) => [...prev, ...data.messages])
    setInput('')
  }

  const finishSession = async () => {
    if (!session) return
    const { data } = await api.post(`/chat/${session.session_id}/finish`)
    setEvaluation(data)
  }

  return (
    <div className="grid two wider-left">
      <div className="card">
        <h2>AI Patient Simulator</h2>
        <p className="muted">Select a patient scenario and practice therapeutic communication.</p>
        <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
          {scenarios.map((scenario) => (
            <option key={scenario.id} value={scenario.id}>{scenario.title}</option>
          ))}
        </select>
        <button onClick={startSession}>Start Session</button>
        <div className="chat-box">
          {messages.map((msg) => (
            <div key={msg.id + msg.timestamp} className={`chat-msg ${msg.sender}`}>
              <strong>{msg.sender === 'patient_ai' ? 'Patient' : 'You'}</strong>
              <p>{msg.message_text}</p>
            </div>
          ))}
        </div>
        <div className="row">
          <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Type your response..." />
          <button onClick={sendMessage}>Send</button>
        </div>
        <button className="secondary-btn" onClick={finishSession}>Finish and Evaluate</button>
      </div>
      <div className="card">
        <h3>Evaluation</h3>
        {!evaluation ? <p className="muted">Finish a session to view your score and feedback.</p> : (
          <>
            <p><strong>Overall Score:</strong> {evaluation.evaluation.overall_score}/120</p>
            <ul>
              <li>Empathy: {evaluation.evaluation.empathy_score}</li>
              <li>Open-ended questions: {evaluation.evaluation.open_ended_score}</li>
              <li>Active listening: {evaluation.evaluation.active_listening_score}</li>
              <li>Clarity: {evaluation.evaluation.clarity_score}</li>
              <li>Professionalism: {evaluation.evaluation.professionalism_score}</li>
            </ul>
            <h4>Strengths</h4>
            <ul>{evaluation.evaluation.strengths.map((item, idx) => <li key={idx}>{item}</li>)}</ul>
            <h4>Areas for improvement</h4>
            <ul>{evaluation.evaluation.areas_for_improvement.map((item, idx) => <li key={idx}>{item}</li>)}</ul>
            <h4>Improved response examples</h4>
            <ul>{evaluation.evaluation.improved_response_examples.map((item, idx) => <li key={idx}>{item}</li>)}</ul>
          </>
        )}
      </div>
    </div>
  )
}
