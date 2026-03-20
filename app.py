import os
from datetime import datetime
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    section = db.Column(db.String(50), nullable=True)
    specialization = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="active")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    attempts = db.relationship("Attempt", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Scenario(db.Model):
    __tablename__ = "scenarios"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    scenario_type = db.Column(db.String(30), nullable=False, default="chat")
    category = db.Column(db.String(100), nullable=False)
    patient_name = db.Column(db.String(100), nullable=False)
    patient_age = db.Column(db.Integer, nullable=True)
    emotional_state = db.Column(db.String(100), nullable=False)
    clinical_context = db.Column(db.Text, nullable=False)
    opening_statement = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(30), nullable=False, default="Beginner")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    attempts = db.relationship("Attempt", backref="scenario", lazy=True, cascade="all, delete-orphan")


class Attempt(db.Model):
    __tablename__ = "attempts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    scenario_id = db.Column(db.Integer, db.ForeignKey("scenarios.id"), nullable=False)
    student_response = db.Column(db.Text, nullable=False)
    ai_feedback = db.Column(db.Text, nullable=False)
    score = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


def create_app():
    app = Flask(__name__)

    secret_key = os.getenv("SECRET_KEY", "dev-secret-key")
    database_url = os.getenv("DATABASE_URL", "sqlite:///theracomm.db")

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://") and "+psycopg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    app.config["SECRET_KEY"] = secret_key
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    engine_connect_args = {}
    if database_url.startswith("postgresql+psycopg://"):
        engine_connect_args = {"prepare_threshold": None, "sslmode": "require"}
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": engine_connect_args,
        "pool_pre_ping": True,
    }

    db.init_app(app)

    with app.app_context():
        db.create_all()
        seed_defaults()

    @app.context_processor
    def inject_globals():
        return {
            "current_user_name": session.get("user_name"),
            "current_user_role": session.get("user_role"),
        }

    def login_required(role=None):
        def decorator(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                if "user_id" not in session:
                    flash("Please log in first.", "warning")
                    return redirect(url_for("login"))
                if role and session.get("user_role") != role:
                    flash("You are not authorized to access that page.", "danger")
                    return redirect(url_for("home"))
                return fn(*args, **kwargs)
            return wrapper
        return decorator

    @app.route("/")
    def home():
        role = session.get("user_role")
        if role == "student":
            return redirect(url_for("student_dashboard"))
        if role == "faculty":
            return redirect(url_for("faculty_dashboard"))
        if role == "manager":
            return redirect(url_for("manager_dashboard"))
        return redirect(url_for("login"))

    @app.route("/health")
    def health():
        return {"status": "ok", "service": "TheraComm AI"}

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                session["user_id"] = user.id
                session["user_name"] = user.full_name
                session["user_role"] = user.role
                flash(f"Welcome, {user.full_name}!", "success")
                return redirect(url_for("home"))
            flash("Invalid credentials.", "danger")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "info")
        return redirect(url_for("login"))

    @app.route("/student")
    @login_required(role="student")
    def student_dashboard():
        scenarios = Scenario.query.order_by(Scenario.id.asc()).all()
        attempts = Attempt.query.filter_by(user_id=session["user_id"]).order_by(Attempt.created_at.desc()).all()
        avg_score = round(sum(a.score for a in attempts) / len(attempts), 1) if attempts else 0
        return render_template("student_dashboard.html", scenarios=scenarios, attempts=attempts, avg_score=avg_score)

    @app.route("/faculty")
    @login_required(role="faculty")
    def faculty_dashboard():
        students = User.query.filter_by(role="student").order_by(User.full_name.asc()).all()
        attempts = Attempt.query.order_by(Attempt.created_at.desc()).all()
        avg_score = round(sum(a.score for a in attempts) / len(attempts), 1) if attempts else 0
        total_students = len(students)
        return render_template("faculty_dashboard.html", students=students, attempts=attempts, avg_score=avg_score, total_students=total_students)

    @app.route("/manager")
    @login_required(role="manager")
    def manager_dashboard():
        users = User.query.order_by(User.role.asc(), User.full_name.asc()).all()
        scenarios = Scenario.query.order_by(Scenario.id.asc()).all()
        attempts = Attempt.query.count()
        return render_template("manager_dashboard.html", users=users, scenarios=scenarios, attempts=attempts)

    @app.route("/users", methods=["GET", "POST"])
    @login_required(role="manager")
    def users_page():
        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            role = request.form.get("role", "student")
            section = request.form.get("section", "").strip() or None
            specialization = request.form.get("specialization", "").strip() or None

            if not full_name or not email or not password:
                flash("Full name, email, and password are required.", "danger")
            elif User.query.filter_by(email=email).first():
                flash("Email already exists.", "warning")
            else:
                user = User(
                    full_name=full_name,
                    email=email,
                    role=role,
                    section=section,
                    specialization=specialization,
                    status="active",
                )
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash("User created successfully.", "success")
                return redirect(url_for("users_page"))

        users = User.query.order_by(User.role.asc(), User.full_name.asc()).all()
        return render_template("users.html", users=users)

    @app.route("/scenarios")
    @login_required()
    def scenarios_page():
        scenarios = Scenario.query.order_by(Scenario.id.asc()).all()
        return render_template("scenarios.html", scenarios=scenarios)

    @app.route("/simulator/<int:scenario_id>", methods=["GET", "POST"])
    @login_required(role="student")
    def simulator(scenario_id):
        scenario = Scenario.query.get_or_404(scenario_id)
        feedback = None
        score = None
        student_response = ""

        if request.method == "POST":
            student_response = request.form.get("student_response", "").strip()
            if not student_response:
                flash("Please enter your therapeutic response.", "warning")
            else:
                feedback, score = evaluate_response(scenario, student_response)
                attempt = Attempt(
                    user_id=session["user_id"],
                    scenario_id=scenario.id,
                    student_response=student_response,
                    ai_feedback=feedback,
                    score=score,
                )
                db.session.add(attempt)
                db.session.commit()
                flash("Response evaluated successfully.", "success")

        return render_template("simulator.html", scenario=scenario, feedback=feedback, score=score, student_response=student_response)

    @app.route("/results")
    @login_required(role="student")
    def results_page():
        attempts = Attempt.query.filter_by(user_id=session["user_id"]).order_by(Attempt.created_at.desc()).all()
        return render_template("results.html", attempts=attempts)

    return app


def seed_defaults():
    if User.query.count() == 0:
        demo_users = [
            ("System Manager", "manager@theracomm.ai", "Manager123!", "manager", None, "Program Management"),
            ("Faculty Evaluator", "faculty@theracomm.ai", "Faculty123!", "faculty", "BSN 4A", "Therapeutic Communication"),
            ("Student Demo", "student@theracomm.ai", "Student123!", "student", "BSN 4A", None),
        ]
        for full_name, email, password, role, section, specialization in demo_users:
            user = User(
                full_name=full_name,
                email=email,
                role=role,
                section=section,
                specialization=specialization,
                status="active",
            )
            user.set_password(password)
            db.session.add(user)
        db.session.commit()

    if Scenario.query.count() == 0:
        scenarios = [
            Scenario(
                title="Anxious Mother of a Febrile Child",
                scenario_type="chat",
                category="Pediatric Nursing",
                patient_name="Mrs. Santos",
                patient_age=32,
                emotional_state="Anxious",
                clinical_context="A mother is worried because her 4-year-old child has fever and has been crying in the pediatric ward.",
                opening_statement="Nurse, I am really scared. My child keeps crying and the fever is not going away.",
                difficulty="Beginner",
            ),
            Scenario(
                title="Preoperative Fear",
                scenario_type="chat",
                category="Medical-Surgical Nursing",
                patient_name="Mr. Reyes",
                patient_age=54,
                emotional_state="Fearful",
                clinical_context="An adult patient is scheduled for surgery tomorrow and is expressing fear and uncertainty.",
                opening_statement="I do not think I can go through with this operation. What if something goes wrong?",
                difficulty="Intermediate",
            ),
            Scenario(
                title="Adolescent Refusing Treatment",
                scenario_type="chat",
                category="Adolescent Health",
                patient_name="Jamie",
                patient_age=16,
                emotional_state="Defensive",
                clinical_context="An adolescent patient is upset and does not want to cooperate with the prescribed care plan.",
                opening_statement="I do not want this anymore. Everyone keeps telling me what to do.",
                difficulty="Intermediate",
            ),
        ]
        db.session.add_all(scenarios)
        db.session.commit()


def evaluate_response(scenario: Scenario, student_response: str):
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key and OpenAI is not None:
        try:
            client = OpenAI(api_key=api_key)
            prompt = f"""
You are evaluating a nursing student's therapeutic communication response.

Scenario title: {scenario.title}
Patient opening statement: {scenario.opening_statement}
Context: {scenario.clinical_context}
Student response: {student_response}

Give:
1. A score from 0 to 100.
2. A short feedback paragraph.
3. Two brief suggestions.

Return in this exact format:
SCORE: <number>
FEEDBACK: <text>
SUGGESTIONS: <text>
"""
            response = client.responses.create(
                model="gpt-4.1-mini",
                input=prompt,
            )
            text = response.output_text.strip()
            parsed_score = 75
            feedback = text
            for line in text.splitlines():
                if line.upper().startswith("SCORE:"):
                    try:
                        parsed_score = int(line.split(":", 1)[1].strip())
                    except Exception:
                        parsed_score = 75
            return feedback, max(0, min(parsed_score, 100))
        except Exception:
            pass

    lower = student_response.lower()
    score = 50
    strengths = []
    suggestions = []

    empathy_words = ["understand", "sorry", "can see", "worried", "feel", "scared"]
    exploratory_words = ["can you tell me", "what", "how", "more about"]
    non_therapeutic = ["don't worry", "calm down", "it's okay", "you should not"]

    if any(word in lower for word in empathy_words):
        score += 20
        strengths.append("Shows empathy or validation.")
    else:
        suggestions.append("Add an empathic statement to acknowledge the patient's feelings.")

    if any(word in lower for word in exploratory_words):
        score += 20
        strengths.append("Uses an open-ended or exploratory question.")
    else:
        suggestions.append("Use an open-ended question to explore the patient's concern further.")

    if any(word in lower for word in non_therapeutic):
        score -= 20
        suggestions.append("Avoid false reassurance or dismissive phrasing.")
    else:
        strengths.append("Avoids obvious non-therapeutic reassurance.")

    if len(student_response.split()) >= 10:
        score += 10
        strengths.append("Provides a reasonably complete response.")
    else:
        suggestions.append("Expand the response slightly to sound more supportive and professional.")

    score = max(0, min(score, 100))
    feedback = f"Score: {score}/100. "
    if strengths:
        feedback += "Strengths: " + " ".join(strengths) + " "
    if suggestions:
        feedback += "Suggestions: " + " ".join(suggestions)
    return feedback, score


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
