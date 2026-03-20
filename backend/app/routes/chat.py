from datetime import datetime
from flask import Blueprint, request
from .. import db
from ..models import Scenario, ChatSession, ChatMessage, Evaluation
from ..services.ai_service import generate_patient_reply, evaluate_conversation
from ..utils.auth import token_required

chat_bp = Blueprint('chat', __name__)


@chat_bp.post('/start')
@token_required(role='student')
def start_chat():
    data = request.get_json() or {}
    scenario = Scenario.query.get_or_404(data.get('scenario_id'))
    if scenario.scenario_type != 'chat':
        return {'error': 'Invalid scenario type'}, 400

    session = ChatSession(student_id=request.current_user.id, scenario_id=scenario.id)
    db.session.add(session)
    db.session.flush()

    opening = ChatMessage(chat_session_id=session.id, sender='patient_ai', message_text=scenario.opening_statement)
    db.session.add(opening)
    db.session.commit()

    return {
        'session_id': session.id,
        'scenario': scenario.to_dict(),
        'messages': [opening.to_dict()],
    }


@chat_bp.get('/<int:session_id>')
@token_required()
def get_chat(session_id):
    session = ChatSession.query.get_or_404(session_id)
    return {
        'session_id': session.id,
        'status': session.status,
        'messages': [m.to_dict() for m in session.messages],
    }


@chat_bp.post('/<int:session_id>/message')
@token_required(role='student')
def send_message(session_id):
    session = ChatSession.query.get_or_404(session_id)
    if session.status != 'in_progress':
        return {'error': 'Session already ended'}, 400

    data = request.get_json() or {}
    student_text = (data.get('message') or '').strip()
    if not student_text:
        return {'error': 'Message is required'}, 400

    student_msg = ChatMessage(chat_session_id=session.id, sender='student', message_text=student_text)
    db.session.add(student_msg)
    db.session.flush()

    history = [m.to_dict() for m in session.messages] + [student_msg.to_dict()]
    scenario = Scenario.query.get(session.scenario_id)
    patient_reply = generate_patient_reply(scenario, history, student_text)
    patient_msg = ChatMessage(chat_session_id=session.id, sender='patient_ai', message_text=patient_reply)
    db.session.add(patient_msg)
    db.session.commit()

    return {'messages': [student_msg.to_dict(), patient_msg.to_dict()]}


@chat_bp.post('/<int:session_id>/finish')
@token_required(role='student')
def finish_chat(session_id):
    session = ChatSession.query.get_or_404(session_id)
    if session.status == 'completed' and session.evaluation:
        return {'evaluation': session.evaluation.to_dict(), 'feedback_summary': session.feedback_summary}

    messages = [m.to_dict() for m in session.messages]
    result = evaluate_conversation(messages)

    evaluation = Evaluation(
        chat_session_id=session.id,
        empathy_score=result['empathy_score'],
        open_ended_score=result['open_ended_score'],
        active_listening_score=result['active_listening_score'],
        clarity_score=result['clarity_score'],
        professionalism_score=result['professionalism_score'],
        overall_score=result['overall_score'],
        strengths='\n'.join(result['strengths']),
        areas_for_improvement='\n'.join(result['areas_for_improvement']),
        improved_response_examples='\n'.join(result['improved_response_examples']),
    )
    db.session.add(evaluation)

    session.status = 'completed'
    session.ended_at = datetime.utcnow()
    session.overall_score = result['overall_score']
    session.feedback_summary = result['feedback_summary']

    db.session.commit()

    return {'evaluation': evaluation.to_dict(), 'feedback_summary': session.feedback_summary}
