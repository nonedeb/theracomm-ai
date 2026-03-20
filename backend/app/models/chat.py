from datetime import datetime
from .. import db


class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='in_progress')
    overall_score = db.Column(db.Integer, nullable=True)
    feedback_summary = db.Column(db.Text, nullable=True)

    messages = db.relationship('ChatMessage', backref='session', lazy=True, cascade='all, delete-orphan')
    evaluation = db.relationship('Evaluation', backref='session', uselist=False, cascade='all, delete-orphan')


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    chat_session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id'), nullable=False)
    sender = db.Column(db.String(20), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'sender': self.sender,
            'message_text': self.message_text,
            'timestamp': self.timestamp.isoformat(),
        }


class Evaluation(db.Model):
    __tablename__ = 'evaluations'

    id = db.Column(db.Integer, primary_key=True)
    chat_session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id'), nullable=False, unique=True)
    empathy_score = db.Column(db.Integer, nullable=False)
    open_ended_score = db.Column(db.Integer, nullable=False)
    active_listening_score = db.Column(db.Integer, nullable=False)
    clarity_score = db.Column(db.Integer, nullable=False)
    professionalism_score = db.Column(db.Integer, nullable=False)
    overall_score = db.Column(db.Integer, nullable=False)
    strengths = db.Column(db.Text, nullable=False)
    areas_for_improvement = db.Column(db.Text, nullable=False)
    improved_response_examples = db.Column(db.Text, nullable=False)
    evaluated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'empathy_score': self.empathy_score,
            'open_ended_score': self.open_ended_score,
            'active_listening_score': self.active_listening_score,
            'clarity_score': self.clarity_score,
            'professionalism_score': self.professionalism_score,
            'overall_score': self.overall_score,
            'strengths': self.strengths.split('\n'),
            'areas_for_improvement': self.areas_for_improvement.split('\n'),
            'improved_response_examples': self.improved_response_examples.split('\n'),
        }
