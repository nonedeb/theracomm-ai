from datetime import datetime
from .. import db


class Scenario(db.Model):
    __tablename__ = 'scenarios'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    patient_name = db.Column(db.String(120), nullable=False)
    patient_age = db.Column(db.Integer, nullable=False)
    clinical_context = db.Column(db.Text, nullable=False)
    emotional_state = db.Column(db.String(80), nullable=False)
    chief_concern = db.Column(db.Text, nullable=False)
    difficulty_level = db.Column(db.String(20), nullable=False, default='basic')
    opening_statement = db.Column(db.Text, nullable=False)
    scenario_type = db.Column(db.String(20), nullable=False, default='chat')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    choices = db.relationship('ScenarioChoice', backref='scenario', lazy=True, cascade='all, delete-orphan')

    def to_dict(self, include_choices=False):
        payload = {
            'id': self.id,
            'title': self.title,
            'category': self.category,
            'patient_name': self.patient_name,
            'patient_age': self.patient_age,
            'clinical_context': self.clinical_context,
            'emotional_state': self.emotional_state,
            'chief_concern': self.chief_concern,
            'difficulty_level': self.difficulty_level,
            'opening_statement': self.opening_statement,
            'scenario_type': self.scenario_type,
        }
        if include_choices:
            payload['choices'] = [choice.to_dict() for choice in self.choices]
        return payload


class ScenarioChoice(db.Model):
    __tablename__ = 'scenario_choices'

    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    choice_text = db.Column(db.Text, nullable=False)
    is_best_answer = db.Column(db.Boolean, default=False)
    rationale = db.Column(db.Text, nullable=False)
    classification = db.Column(db.String(40), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'choice_text': self.choice_text,
            'is_best_answer': self.is_best_answer,
            'rationale': self.rationale,
            'classification': self.classification,
        }
