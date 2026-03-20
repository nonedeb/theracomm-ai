from flask import Blueprint
from sqlalchemy import func
from ..models import User, ChatSession, Evaluation, DecisionAttempt
from ..utils.auth import token_required

faculty_bp = Blueprint('faculty', __name__)


@faculty_bp.get('/analytics')
@token_required(role='faculty')
def analytics():
    students_count = User.query.filter_by(role='student').count()
    avg_chat = func.avg(Evaluation.overall_score)
    avg_decision = func.avg(DecisionAttempt.score)

    avg_chat_score = round((db_value := (Evaluation.query.with_entities(avg_chat).scalar() or 0)), 1)
    avg_decision_score = round((DecisionAttempt.query.with_entities(avg_decision).scalar() or 0), 1)

    recent_sessions = (
        ChatSession.query.order_by(ChatSession.started_at.desc()).limit(10).all()
    )

    weak_skill = 'Empathy reinforcement needed'
    if avg_chat_score >= 85:
        weak_skill = 'Maintain reflective listening drills'
    elif avg_chat_score >= 70:
        weak_skill = 'Improve open-ended questioning'

    return {
        'summary': {
            'students_count': students_count,
            'average_chat_score': avg_chat_score,
            'average_decision_score': avg_decision_score,
            'students_needing_support': len([s for s in recent_sessions if (s.overall_score or 0) < 75]),
            'common_weak_skill': weak_skill,
        },
        'recent_sessions': [
            {
                'session_id': s.id,
                'student_id': s.student_id,
                'scenario_id': s.scenario_id,
                'overall_score': s.overall_score,
                'status': s.status,
            }
            for s in recent_sessions
        ],
    }
