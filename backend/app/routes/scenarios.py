from flask import Blueprint, request
from .. import db
from ..models import Scenario, ScenarioChoice, DecisionAttempt
from ..utils.auth import token_required

scenarios_bp = Blueprint('scenarios', __name__)


@scenarios_bp.get('/')
@token_required()
def list_scenarios():
    scenario_type = request.args.get('type')
    query = Scenario.query
    if scenario_type:
        query = query.filter_by(scenario_type=scenario_type)
    return {'scenarios': [s.to_dict() for s in query.order_by(Scenario.id).all()]}


@scenarios_bp.get('/<int:scenario_id>')
@token_required()
def get_scenario(scenario_id):
    scenario = Scenario.query.get_or_404(scenario_id)
    return {'scenario': scenario.to_dict(include_choices=True)}


@scenarios_bp.post('/<int:scenario_id>/submit')
@token_required(role='student')
def submit_decision(scenario_id):
    scenario = Scenario.query.get_or_404(scenario_id)
    if scenario.scenario_type != 'decision':
        return {'error': 'Invalid scenario type'}, 400

    data = request.get_json() or {}
    choice = ScenarioChoice.query.filter_by(id=data.get('choice_id'), scenario_id=scenario_id).first()
    if not choice:
        return {'error': 'Choice not found'}, 404

    score = 100 if choice.is_best_answer else (70 if choice.classification == 'partially_therapeutic' else 40)
    attempt = DecisionAttempt(
        student_id=request.current_user.id,
        scenario_id=scenario_id,
        selected_choice_id=choice.id,
        is_correct=choice.is_best_answer,
        score=score,
    )
    db.session.add(attempt)
    db.session.commit()

    return {
        'result': {
            'is_correct': choice.is_best_answer,
            'score': score,
            'selected_choice_id': choice.id,
            'classification': choice.classification,
            'rationale': choice.rationale,
            'best_choice_id': next((c.id for c in scenario.choices if c.is_best_answer), None),
        }
    }
