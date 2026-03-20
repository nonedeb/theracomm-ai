import os
from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()


def _normalize_database_url(url: str | None) -> str:
    if not url:
        return 'sqlite:///theracomm.db'

    normalized = url.strip()

    # Render / Supabase friendly normalization
    if normalized.startswith('postgres://'):
        normalized = normalized.replace('postgres://', 'postgresql+psycopg2://', 1)
    elif normalized.startswith('postgresql://') and '+psycopg2' not in normalized:
        normalized = normalized.replace('postgresql://', 'postgresql+psycopg2://', 1)

    if 'supabase.co' in normalized and 'sslmode=' not in normalized:
        normalized += ('&' if '?' in normalized else '?') + 'sslmode=require'

    return normalized


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret')
    app.config['SQLALCHEMY_DATABASE_URI'] = _normalize_database_url(os.getenv('DATABASE_URL'))
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
    }

    allowed_origins = os.getenv('CORS_ORIGINS', '*')
    CORS(app, resources={r'/api/*': {'origins': '*' if allowed_origins == '*' else [o.strip() for o in allowed_origins.split(',') if o.strip()]}})
    db.init_app(app)

    from .models import User, Scenario, ScenarioChoice, ChatSession, ChatMessage, Evaluation, DecisionAttempt

    with app.app_context():
        db.create_all()
        from .utils.seed import seed_database
        seed_database(db)

    from .routes.auth import auth_bp
    from .routes.scenarios import scenarios_bp
    from .routes.chat import chat_bp
    from .routes.faculty import faculty_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(scenarios_bp, url_prefix='/api/scenarios')
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    app.register_blueprint(faculty_bp, url_prefix='/api/faculty')

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'app': 'TheraComm AI'}

    return app
