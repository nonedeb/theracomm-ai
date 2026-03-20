from functools import wraps
from flask import current_app, request
import jwt
from ..models import User


def generate_token(user):
    payload = {'user_id': user.id, 'role': user.role}
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')


def token_required(role=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return {'error': 'Missing token'}, 401
            token = auth_header.split(' ')[1]
            try:
                payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
                user = User.query.get(payload['user_id'])
                if not user:
                    return {'error': 'User not found'}, 401
                if role and user.role != role:
                    return {'error': 'Forbidden'}, 403
                request.current_user = user
            except jwt.InvalidTokenError:
                return {'error': 'Invalid token'}, 401
            return func(*args, **kwargs)
        return wrapper
    return decorator
