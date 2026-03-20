from flask import Blueprint, request
from .. import db
from ..models import User
from ..utils.auth import generate_token, token_required

auth_bp = Blueprint('auth', __name__)


@auth_bp.post('/register')
def register():
    data = request.get_json() or {}
    required = ['full_name', 'email', 'password', 'role']
    if not all(data.get(field) for field in required):
        return {'error': 'Missing required fields'}, 400
    if User.query.filter_by(email=data['email']).first():
        return {'error': 'Email already exists'}, 409

    user = User(
        full_name=data['full_name'],
        email=data['email'],
        role=data['role'],
        year_level=data.get('year_level'),
        section=data.get('section'),
    )
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()

    return {'token': generate_token(user), 'user': user.to_dict()}, 201


@auth_bp.post('/login')
def login():
    data = request.get_json() or {}
    user = User.query.filter_by(email=data.get('email')).first()
    if not user or not user.check_password(data.get('password', '')):
        return {'error': 'Invalid credentials'}, 401
    return {'token': generate_token(user), 'user': user.to_dict()}


@auth_bp.get('/me')
@token_required()
def me():
    return {'user': request.current_user.to_dict()}
