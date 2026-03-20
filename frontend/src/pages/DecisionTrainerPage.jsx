import { useEffect, useState } from 'react'
import api from '../services/api'

export default function DecisionTrainerPage() {
  const [scenario, setScenario] = useState(null)
  const [selectedChoice, setSelectedChoice] = useState(null)
  const [result, setResult] = useState(null)

  useEffect(() => {
    api.get('/scenarios?type=decision').then(async ({ data }) => {
      if (data.scenarios[0]) {
        const full = await api.get(`/scenarios/${data.scenarios[0].id}`)
        setScenario(full.data.scenario)
      }
    })
  }, [])

  const submit = async () => {
    if (!selectedChoice || !scenario) return
    const { data } = await api.post(`/scenarios/${scenario.id}/submit`, { choice_id: selectedChoice })
    setResult(data.result)
  }

  return (
    <div className="card">
      <h2>Scenario-Based Decision Trainer</h2>
      {!scenario ? <p>Loading scenario...</p> : (
        <>
          <p className="muted">{scenario.title}</p>
          <div className="scenario-box">
            <p><strong>Context:</strong> {scenario.clinical_context}</p>
            <p><strong>Patient says:</strong> {scenario.opening_statement}</p>
          </div>
          <div className="choices">
            {scenario.choices.map((choice) => (
              <label key={choice.id} className="choice-item">
                <input type="radio" name="choice" checked={selectedChoice === choice.id} onChange={() => setSelectedChoice(choice.id)} />
                <span>{choice.choice_text}</span>
              </label>
            ))}
          </div>
          <button onClick={submit}>Submit Answer</button>
          {result && (
            <div className="feedback-panel">
              <p><strong>Score:</strong> {result.score}/100</p>
              <p><strong>Classification:</strong> {result.classification}</p>
              <p><strong>Rationale:</strong> {result.rationale}</p>
              <p><strong>Result:</strong> {result.is_correct ? 'Best therapeutic answer selected.' : 'Review the therapeutic choice and rationale.'}</p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
