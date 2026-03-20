import json
import os
from datetime import datetime
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

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
    section = db.Column(db.String(50))
    specialization = db.Column(db.String(100))
    status = db.Column(db.String(20), nullable=False, default="active")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    attempts = db.relationship("Attempt", backref="user", lazy=True, cascade="all, delete-orphan")
    assessment_sessions = db.relationship("AssessmentSession", backref="user", lazy=True, cascade="all, delete-orphan", foreign_keys='AssessmentSession.user_id')
    reviews_made = db.relationship("AssessmentSession", lazy=True, foreign_keys='AssessmentSession.reviewed_by')

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Scenario(db.Model):
    __tablename__ = "scenarios"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    scenario_type = db.Column(db.String(30), nullable=False, default="chat")  # chat / decision
    category = db.Column(db.String(100), nullable=False)
    patient_name = db.Column(db.String(100), nullable=False)
    patient_age = db.Column(db.Integer)
    emotional_state = db.Column(db.String(100), nullable=False)
    clinical_context = db.Column(db.Text, nullable=False)
    opening_statement = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(30), nullable=False, default="Beginner")
    choices_json = db.Column(db.Text)
    correct_choice = db.Column(db.Integer)
    rationale = db.Column(db.Text)
    source_type = db.Column(db.String(30), nullable=False, default="seeded")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Attempt(db.Model):
    __tablename__ = "attempts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    scenario_id = db.Column(db.Integer, db.ForeignKey("scenarios.id"), nullable=False)
    student_response = db.Column(db.Text, nullable=False)
    ai_feedback = db.Column(db.Text, nullable=False)
    score = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    scenario = db.relationship("Scenario")


class AssessmentSession(db.Model):
    __tablename__ = "assessment_sessions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    total_score = db.Column(db.Integer, default=0)
    interpretation = db.Column(db.String(100))
    overall_feedback = db.Column(db.Text)
    faculty_comment = db.Column(db.Text)
    faculty_recommendation = db.Column(db.Text)
    review_status = db.Column(db.String(20), nullable=False, default="pending")
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewed_at = db.Column(db.DateTime)

    answers = db.relationship("AssessmentAnswer", backref="assessment_session", lazy=True, cascade="all, delete-orphan")
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])


class AssessmentAnswer(db.Model):
    __tablename__ = "assessment_answers"
    id = db.Column(db.Integer, primary_key=True)
    assessment_session_id = db.Column(db.Integer, db.ForeignKey("assessment_sessions.id"), nullable=False)
    scenario_id = db.Column(db.Integer, db.ForeignKey("scenarios.id"), nullable=False)
    response_type = db.Column(db.String(20), nullable=False)
    student_answer = db.Column(db.Text, nullable=False)
    ai_feedback = db.Column(db.Text)
    score = db.Column(db.Integer, default=0)

    scenario = db.relationship("Scenario")


class LibraryFile(db.Model):
    __tablename__ = "library_files"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    filename = db.Column(db.String(255), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    uploader = db.relationship("User")


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")

    database_url = os.getenv("DATABASE_URL", "sqlite:///theracomm_v12.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://") and "+psycopg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    connect_args = {}
    if database_url.startswith("postgresql+psycopg://"):
        connect_args = {"prepare_threshold": None, "sslmode": "require", "connect_timeout": 5}
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": connect_args, "pool_pre_ping": True}

    upload_folder = os.path.join(app.root_path, "static", "uploads")
    os.makedirs(upload_folder, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = upload_folder

    db.init_app(app)

    @app.template_filter("from_json")
    def from_json_filter(value):
        try:
            return json.loads(value or "[]")
        except Exception:
            return []

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
        return "ok", 200

    @app.route("/init-db")
    def init_db():
        try:
            db.create_all()
            seed_defaults()
            return "Database initialized successfully.", 200
        except Exception as e:
            return f"Init DB error: {e}", 500

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email, status="active").first()
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
        flash("Logged out.", "info")
        return redirect(url_for("login"))

    @app.route("/student")
    @login_required(role="student")
    def student_dashboard():
        total_attempts = Attempt.query.filter_by(user_id=session["user_id"]).count()
        assessments = AssessmentSession.query.filter_by(user_id=session["user_id"]).order_by(AssessmentSession.started_at.desc()).all()
        avg_score = round(sum(a.total_score for a in assessments if a.completed_at) / len([a for a in assessments if a.completed_at]), 1) if any(a.completed_at for a in assessments) else 0
        return render_template("student_dashboard.html", total_attempts=total_attempts, assessments=assessments, avg_score=avg_score)

    @app.route("/chat")
    @login_required(role="student")
    def chat_sessions():
        scenarios = Scenario.query.filter_by(scenario_type="chat", is_active=True).order_by(Scenario.id.asc()).all()
        return render_template("chat_sessions.html", scenarios=scenarios)

    @app.route("/decision")
    @login_required(role="student")
    def decision_sessions():
        scenarios = Scenario.query.filter_by(scenario_type="decision", is_active=True).order_by(Scenario.id.asc()).all()
        return render_template("decision_sessions.html", scenarios=scenarios)

    @app.route("/simulator/<int:scenario_id>", methods=["GET", "POST"])
    @login_required(role="student")
    def simulator(scenario_id):
        scenario = Scenario.query.get_or_404(scenario_id)
        feedback = None
        score = None
        student_response = ""
        patient_reply = None
        if request.method == "POST":
            student_response = request.form.get("student_response", "").strip()
            if student_response:
                feedback, score = evaluate_response(scenario, student_response)
                patient_reply = generate_patient_reply(scenario, student_response)
                attempt = Attempt(user_id=session["user_id"], scenario_id=scenario.id, student_response=student_response, ai_feedback=feedback, score=score)
                db.session.add(attempt)
                db.session.commit()
                flash("Chat session evaluated.", "success")
            else:
                flash("Please enter a response.", "warning")
        return render_template("simulator.html", scenario=scenario, feedback=feedback, score=score, patient_reply=patient_reply, student_response=student_response)

    @app.route("/decision/<int:scenario_id>", methods=["GET", "POST"])
    @login_required(role="student")
    def decision_detail(scenario_id):
        scenario = Scenario.query.get_or_404(scenario_id)
        choices = json.loads(scenario.choices_json or "[]")
        selected = None
        result = None
        score = None
        if request.method == "POST":
            selected = request.form.get("selected_choice")
            if selected is None:
                flash("Choose an answer.", "warning")
            else:
                idx = int(selected)
                if idx == scenario.correct_choice:
                    score = 100
                    result = f"Correct. {scenario.rationale or 'This is the most therapeutic response.'}"
                else:
                    score = 40
                    result = f"Not the best choice. {scenario.rationale or 'Review therapeutic communication principles.'}"
                attempt = Attempt(user_id=session["user_id"], scenario_id=scenario.id, student_response=choices[idx], ai_feedback=result, score=score)
                db.session.add(attempt)
                db.session.commit()
        return render_template("decision_detail.html", scenario=scenario, choices=choices, selected=selected, result=result, score=score)

    @app.route("/assessment/start")
    @login_required(role="student")
    def start_assessment():
        chat_scenarios = Scenario.query.filter_by(scenario_type="chat", is_active=True).limit(10).all()
        decision_scenarios = Scenario.query.filter_by(scenario_type="decision", is_active=True).limit(10).all()
        scenarios = chat_scenarios + decision_scenarios
        if len(scenarios) < 20:
            flash("At least 20 scenarios are needed. Visit /init-db or add more scenarios.", "warning")
            return redirect(url_for("student_dashboard"))
        assessment = AssessmentSession(user_id=session["user_id"], review_status="pending")
        db.session.add(assessment)
        db.session.commit()
        for sc in scenarios:
            db.session.add(AssessmentAnswer(assessment_session_id=assessment.id, scenario_id=sc.id, response_type=sc.scenario_type, student_answer=""))
        db.session.commit()
        return redirect(url_for("assessment_take", assessment_id=assessment.id))

    @app.route("/assessment/<int:assessment_id>", methods=["GET", "POST"])
    @login_required(role="student")
    def assessment_take(assessment_id):
        assessment = AssessmentSession.query.get_or_404(assessment_id)
        if assessment.user_id != session["user_id"]:
            flash("Not allowed.", "danger")
            return redirect(url_for("student_dashboard"))
        answers = AssessmentAnswer.query.filter_by(assessment_session_id=assessment.id).all()
        if request.method == "POST":
            total = 0
            strengths = []
            improvements = []
            for ans in answers:
                field_name = f"scenario_{ans.scenario_id}"
                value = request.form.get(field_name, "").strip()
                ans.student_answer = value
                if ans.response_type == "decision":
                    scenario = ans.scenario
                    if value == "":
                        ans.score = 0
                        ans.ai_feedback = "No answer provided."
                    else:
                        chosen = int(value)
                        choices = json.loads(scenario.choices_json or "[]")
                        ans.student_answer = choices[chosen] if choices and chosen < len(choices) else value
                        ans.score = 5 if chosen == scenario.correct_choice else 2
                        ans.ai_feedback = scenario.rationale or "Review the rationale for the most therapeutic answer."
                else:
                    feedback, raw_score = evaluate_response(ans.scenario, value)
                    ans.score = max(0, min(round(raw_score / 20), 5))
                    ans.ai_feedback = feedback
                    if ans.score >= 4:
                        strengths.append(ans.scenario.title)
                    else:
                        improvements.append(ans.scenario.title)
                total += ans.score
            assessment.total_score = total
            assessment.completed_at = datetime.utcnow()
            assessment.interpretation = interpret_score(total)
            assessment.overall_feedback = build_assessment_feedback(total, strengths, improvements)
            db.session.commit()
            flash("Assessment submitted successfully.", "success")
            return redirect(url_for("assessment_result", assessment_id=assessment.id))
        return render_template("assessment_take.html", assessment=assessment, answers=answers)

    @app.route("/assessment/<int:assessment_id>/result")
    @login_required()
    def assessment_result(assessment_id):
        assessment = AssessmentSession.query.get_or_404(assessment_id)
        if session.get("user_role") == "student" and assessment.user_id != session.get("user_id"):
            flash("Not allowed.", "danger")
            return redirect(url_for("home"))
        return render_template("assessment_result.html", assessment=assessment)

    @app.route("/results")
    @login_required(role="student")
    def results_page():
        attempts = Attempt.query.filter_by(user_id=session["user_id"]).order_by(Attempt.created_at.desc()).all()
        assessments = AssessmentSession.query.filter_by(user_id=session["user_id"]).order_by(AssessmentSession.started_at.desc()).all()
        return render_template("results.html", attempts=attempts, assessments=assessments)

    @app.route("/faculty")
    @login_required(role="faculty")
    def faculty_dashboard():
        students = User.query.filter_by(role="student").order_by(User.full_name.asc()).all()
        assessments = AssessmentSession.query.order_by(AssessmentSession.started_at.desc()).all()
        avg_score = round(sum(a.total_score for a in assessments if a.completed_at) / len([a for a in assessments if a.completed_at]), 1) if any(a.completed_at for a in assessments) else 0
        pending = AssessmentSession.query.filter_by(review_status="pending").count()
        return render_template("faculty_dashboard.html", students=students, assessments=assessments[:10], avg_score=avg_score, pending=pending)

    @app.route("/faculty/records")
    @login_required(role="faculty")
    def faculty_records():
        assessments = AssessmentSession.query.order_by(AssessmentSession.started_at.desc()).all()
        return render_template("faculty_records.html", assessments=assessments)

    @app.route("/faculty/review/<int:assessment_id>", methods=["GET", "POST"])
    @login_required(role="faculty")
    def faculty_review(assessment_id):
        assessment = AssessmentSession.query.get_or_404(assessment_id)
        if request.method == "POST":
            assessment.faculty_comment = request.form.get("faculty_comment", "").strip()
            assessment.faculty_recommendation = request.form.get("faculty_recommendation", "").strip()
            assessment.review_status = request.form.get("review_status", "reviewed")
            assessment.reviewed_by = session["user_id"]
            assessment.reviewed_at = datetime.utcnow()
            db.session.commit()
            flash("Faculty review saved.", "success")
            return redirect(url_for("faculty_records"))
        return render_template("faculty_review.html", assessment=assessment)

    @app.route("/manager")
    @login_required(role="manager")
    def manager_dashboard():
        return render_template(
            "manager_dashboard.html",
            total_users=User.query.count(),
            total_scenarios=Scenario.query.count(),
            total_assessments=AssessmentSession.query.count(),
            library_count=LibraryFile.query.count(),
        )

    @app.route("/manager/users", methods=["GET", "POST"])
    @login_required(role="manager")
    def manager_users():
        if request.method == "POST":
            user_id = request.form.get("user_id")
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            role = request.form.get("role", "student")
            section = request.form.get("section", "").strip() or None
            specialization = request.form.get("specialization", "").strip() or None
            status = request.form.get("status", "active")
            password = request.form.get("password", "").strip()
            if user_id:
                user = User.query.get_or_404(int(user_id))
                user.full_name = full_name
                user.email = email
                user.role = role
                user.section = section
                user.specialization = specialization
                user.status = status
                if password:
                    user.set_password(password)
                flash("User updated.", "success")
            else:
                user = User(full_name=full_name, email=email, role=role, section=section, specialization=specialization, status=status)
                user.set_password(password or "Password123!")
                db.session.add(user)
                flash("User added.", "success")
            db.session.commit()
            return redirect(url_for("manager_users"))
        users = User.query.order_by(User.role.asc(), User.full_name.asc()).all()
        edit_id = request.args.get("edit")
        edit_user = User.query.get(int(edit_id)) if edit_id else None
        return render_template("manager_users.html", users=users, edit_user=edit_user)

    @app.route("/manager/users/<int:user_id>/delete")
    @login_required(role="manager")
    def manager_delete_user(user_id):
        user = User.query.get_or_404(user_id)
        if user.email == "manager@theracomm.ai":
            flash("Default manager cannot be deleted.", "warning")
        else:
            db.session.delete(user)
            db.session.commit()
            flash("User deleted.", "info")
        return redirect(url_for("manager_users"))

    @app.route("/manager/scenarios", methods=["GET", "POST"])
    @login_required(role="manager")
    def manager_scenarios():
        if request.method == "POST":
            scenario_id = request.form.get("scenario_id")
            choices_raw = request.form.get("choices", "").strip()
            choices_json = json.dumps([c.strip() for c in choices_raw.split("\n") if c.strip()]) if choices_raw else None
            payload = {
                "title": request.form.get("title", "").strip(),
                "scenario_type": request.form.get("scenario_type", "chat"),
                "category": request.form.get("category", "").strip(),
                "patient_name": request.form.get("patient_name", "").strip(),
                "patient_age": int(request.form.get("patient_age") or 0) or None,
                "emotional_state": request.form.get("emotional_state", "").strip(),
                "clinical_context": request.form.get("clinical_context", "").strip(),
                "opening_statement": request.form.get("opening_statement", "").strip(),
                "difficulty": request.form.get("difficulty", "Beginner"),
                "choices_json": choices_json,
                "correct_choice": int(request.form.get("correct_choice") or 0) if request.form.get("scenario_type") == "decision" else None,
                "rationale": request.form.get("rationale", "").strip(),
                "source_type": request.form.get("source_type", "manager"),
                "is_active": True if request.form.get("is_active") == "on" else False,
            }
            if scenario_id:
                sc = Scenario.query.get_or_404(int(scenario_id))
                for k, v in payload.items():
                    setattr(sc, k, v)
                flash("Scenario updated.", "success")
            else:
                sc = Scenario(**payload)
                db.session.add(sc)
                flash("Scenario added.", "success")
            db.session.commit()
            return redirect(url_for("manager_scenarios"))
        scenarios = Scenario.query.order_by(Scenario.id.desc()).all()
        edit_id = request.args.get("edit")
        edit_scenario = Scenario.query.get(int(edit_id)) if edit_id else None
        return render_template("manager_scenarios.html", scenarios=scenarios, edit_scenario=edit_scenario, json=json)

    @app.route("/manager/scenarios/<int:scenario_id>/delete")
    @login_required(role="manager")
    def manager_delete_scenario(scenario_id):
        sc = Scenario.query.get_or_404(scenario_id)
        db.session.delete(sc)
        db.session.commit()
        flash("Scenario deleted.", "info")
        return redirect(url_for("manager_scenarios"))

    @app.route("/manager/library", methods=["GET", "POST"])
    @login_required(role="manager")
    def manager_library():
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            uploaded = request.files.get("file")
            if not title or not uploaded or not uploaded.filename:
                flash("Title and file are required.", "warning")
            else:
                filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secure_filename(uploaded.filename)}"
                uploaded.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                rec = LibraryFile(title=title, description=description, filename=filename, uploaded_by=session["user_id"])
                db.session.add(rec)
                db.session.commit()
                flash("Library file uploaded.", "success")
                return redirect(url_for("manager_library"))
        files = LibraryFile.query.order_by(LibraryFile.created_at.desc()).all()
        return render_template("manager_library.html", files=files)

    return app


def interpret_score(total):
    if total >= 90:
        return "Highly Effective"
    if total >= 80:
        return "Effective"
    if total >= 70:
        return "Moderately Effective"
    if total >= 60:
        return "Needs Improvement"
    return "Requires Remediation"


def build_assessment_feedback(total, strengths, improvements):
    parts = [f"Overall score: {total}/100."]
    if strengths:
        parts.append("Strengths were observed in: " + ", ".join(strengths[:5]) + ".")
    if improvements:
        parts.append("Further improvement is needed in: " + ", ".join(improvements[:5]) + ".")
    parts.append("Focus on empathy, open-ended questioning, reflective listening, and avoiding false reassurance.")
    return " ".join(parts)


def generate_patient_reply(scenario, student_response):
    lower = student_response.lower()
    if any(x in lower for x in ["tell me more", "can you share", "what worries"]):
        return "I feel a bit relieved that you're listening. I'm mostly worried about what will happen next."
    if any(x in lower for x in ["don't worry", "calm down", "you'll be fine"]):
        return "I know you're trying to help, but I still feel worried and unheard."
    return f"I still feel {scenario.emotional_state.lower()}. I need someone to understand what I'm going through."


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
            response = client.responses.create(model="gpt-4.1-mini", input=prompt)
            text = response.output_text.strip()
            parsed_score = 75
            for line in text.splitlines():
                if line.upper().startswith("SCORE:"):
                    parsed_score = int(line.split(":", 1)[1].strip())
            return text, max(0, min(parsed_score, 100))
        except Exception:
            pass

    lower = student_response.lower()
    score = 45
    strengths = []
    suggestions = []
    empathy_words = ["understand", "sorry", "can see", "worried", "feel", "scared", "hear"]
    exploratory_words = ["can you tell me", "what", "how", "more about", "share"]
    non_therapeutic = ["don't worry", "calm down", "it's okay", "you should not", "just relax"]
    if any(word in lower for word in empathy_words):
        score += 20
        strengths.append("Shows empathy or validation.")
    else:
        suggestions.append("Add an empathic statement.")
    if any(word in lower for word in exploratory_words):
        score += 20
        strengths.append("Uses open-ended exploration.")
    else:
        suggestions.append("Use an open-ended question.")
    if any(word in lower for word in non_therapeutic):
        score -= 20
        suggestions.append("Avoid false reassurance.")
    else:
        strengths.append("Avoids obvious dismissive phrases.")
    if len(student_response.split()) >= 10:
        score += 10
        strengths.append("Provides a reasonably complete response.")
    else:
        suggestions.append("Expand the response slightly.")
    score = max(0, min(score, 100))
    feedback = f"Score: {score}/100. Strengths: {' '.join(strengths)} Suggestions: {' '.join(suggestions)}"
    return feedback, score


def seed_defaults():
    if User.query.count() == 0:
        users = [
            ("System Manager", "manager@theracomm.ai", "Manager123!", "manager", None, "Program Management"),
            ("Faculty Evaluator", "faculty@theracomm.ai", "Faculty123!", "faculty", "BSN 4A", "Therapeutic Communication"),
            ("Student Demo", "student@theracomm.ai", "Student123!", "student", "BSN 4A", None),
        ]
        for full_name, email, password, role, section, specialization in users:
            u = User(full_name=full_name, email=email, role=role, section=section, specialization=specialization, status="active")
            u.set_password(password)
            db.session.add(u)
        db.session.commit()

    if Scenario.query.count() == 0:
        seeded = [
            # chat
            ("Anxious Mother of a Febrile Child", "chat", "Pediatric Nursing", "Mrs. Santos", 32, "Anxious", "A mother is worried because her 4-year-old child has fever.", "Nurse, I am really scared. My child keeps crying and the fever is not going away.", "Beginner", None, None, None),
            ("Preoperative Fear", "chat", "Medical-Surgical Nursing", "Mr. Reyes", 54, "Fearful", "An adult patient is scheduled for surgery tomorrow.", "I do not think I can go through with this operation. What if something goes wrong?", "Intermediate", None, None, None),
            ("Adolescent Refusing Treatment", "chat", "Adolescent Health", "Jamie", 16, "Defensive", "An adolescent patient refuses the care plan.", "I do not want this anymore. Everyone keeps telling me what to do.", "Intermediate", None, None, None),
            ("New Cancer Diagnosis", "chat", "Oncology", "Mr. Cruz", 65, "Overwhelmed", "A patient has just received a serious diagnosis.", "Am I going to die soon?", "Advanced", None, None, None),
            ("Postpartum Distress", "chat", "Maternal Health", "Mrs. Dela Rosa", 27, "Crying", "A postpartum mother feels she is failing as a parent.", "I do not think I am a good mother.", "Intermediate", None, None, None),
            ("Elderly Confusion", "chat", "Geriatric Nursing", "Lola Maria", 78, "Confused", "An elderly patient is disoriented in the ward.", "Why am I here? I want to go home.", "Beginner", None, None, None),
            ("Chronic Pain Frustration", "chat", "Medical-Surgical Nursing", "Ms. Aquino", 41, "Frustrated", "A patient with chronic pain feels no one understands her.", "You all keep saying the same thing. Nothing helps.", "Intermediate", None, None, None),
            ("Pediatric Procedure Anxiety", "chat", "Pediatric Nursing", "Carlo", 9, "Scared", "A child is afraid of an IV insertion.", "Please do not let them hurt me.", "Beginner", None, None, None),
            ("Grieving Family Member", "chat", "End-of-Life Care", "Mrs. Lim", 49, "Grieving", "A family member has just lost a loved one.", "I was not ready to lose him.", "Advanced", None, None, None),
            ("Community Health Stigma", "chat", "Community Health", "Ana", 22, "Ashamed", "A young adult is embarrassed about a health condition.", "I do not want anyone to know what I have.", "Intermediate", None, None, None),
            # decision
            ("Fear of Death", "decision", "Psychiatric Nursing", "Mr. Cruz", 65, "Fearful", "The patient says he is scared of dying.", "I'm scared I might die.", "Beginner", ["Don't worry, you'll be fine.", "Can you tell me what scares you the most right now?", "That's normal.", "You need to stay positive."], 1, "The best response explores the patient's concern with empathy and an open-ended question."),
            ("Angry Relative", "decision", "Medical-Surgical Nursing", "Mrs. Gomez", 38, "Angry", "A family member is upset about waiting time.", "No one here cares about my father!", "Intermediate", ["Please calm down.", "I can see you're upset. Tell me what happened from your perspective.", "You need to be patient.", "There is nothing I can do."], 1, "Validation plus exploration is more therapeutic than defensiveness or dismissal."),
            ("Child Crying Before Procedure", "decision", "Pediatric Nursing", "Mia", 7, "Afraid", "A child is crying before a procedure.", "I don't want the needle!", "Beginner", ["Stop crying.", "Nothing bad will happen.", "You're scared about the needle. Can you tell me what worries you most?", "Be brave now."], 2, "Naming the feeling and inviting expression is therapeutic."),
            ("Adolescent Withdrawal", "decision", "Adolescent Health", "Jay", 15, "Withdrawn", "A teen does not want to talk.", "Leave me alone.", "Intermediate", ["Fine, I will leave.", "You should talk to me.", "I will stay nearby if you want to talk later.", "Why are you acting like this?"], 2, "Offering presence without pressure supports autonomy and trust."),
            ("Postpartum Self-Doubt", "decision", "Maternal Health", "Mrs. Dela Rosa", 27, "Sad", "A mother doubts herself after delivery.", "Maybe my baby deserves a better mother.", "Intermediate", ["That's not true.", "Many mothers feel that way.", "It sounds like you're feeling overwhelmed. Tell me more about what has been hardest.", "You need more sleep."], 2, "Reflecting emotion and exploring the concern is most therapeutic."),
            ("Elderly Disorientation", "decision", "Geriatric Nursing", "Lola Maria", 78, "Confused", "An elderly patient wants to leave the ward.", "I need to go home now.", "Beginner", ["You cannot leave.", "You're confused again.", "You're in the hospital right now, and I will stay with you. What would help you feel safer?", "Just rest."], 2, "Reorientation with reassurance and support is therapeutic."),
            ("Pain Complaint", "decision", "Medical-Surgical Nursing", "Ms. Aquino", 41, "Frustrated", "A patient feels unheard about pain.", "No one listens when I say I'm in pain.", "Intermediate", ["We already gave your medicine.", "I hear that you're frustrated. Tell me more about your pain right now.", "You need to wait.", "It can't be that bad."], 1, "Acknowledging frustration and assessing further is therapeutic."),
            ("Terminal Illness Concern", "decision", "Oncology", "Mr. Cruz", 65, "Fearful", "The patient asks about dying.", "Am I dying?", "Advanced", ["Let's not think about that.", "Why would you say that?", "What thoughts have you had since hearing the diagnosis?", "Everything happens for a reason."], 2, "Open exploration respects emotion and meaning-making."),
            ("Grieving Daughter", "decision", "End-of-Life Care", "Anna", 30, "Grieving", "The daughter blames herself for her parent's death.", "Maybe if I got here sooner, he would still be alive.", "Advanced", ["Don't blame yourself.", "You did the best you could. Tell me more about what you're feeling right now.", "That isn't true.", "Try to rest."], 1, "Validation plus invitation to express feelings is therapeutic."),
            ("Embarrassed Community Client", "decision", "Community Health", "Ana", 22, "Ashamed", "A client is embarrassed about a diagnosis.", "Please don't tell anyone about this.", "Intermediate", ["Why are you ashamed?", "I understand privacy matters to you. What are your biggest worries right now?", "You shouldn't feel that way.", "It's not a big deal."], 1, "The best response validates privacy concerns and explores fears.")
        ]
        for row in seeded:
            title, scenario_type, category, patient_name, patient_age, emotional_state, clinical_context, opening_statement, difficulty, choices, correct_choice, rationale = row
            db.session.add(Scenario(
                title=title,
                scenario_type=scenario_type,
                category=category,
                patient_name=patient_name,
                patient_age=patient_age,
                emotional_state=emotional_state,
                clinical_context=clinical_context,
                opening_statement=opening_statement,
                difficulty=difficulty,
                choices_json=json.dumps(choices) if choices else None,
                correct_choice=correct_choice,
                rationale=rationale,
                source_type="seeded",
                is_active=True,
            ))
        db.session.commit()


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
