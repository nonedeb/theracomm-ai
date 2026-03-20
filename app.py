import csv, io, json, os, random
from datetime import datetime
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


db = SQLAlchemy()

database_url = os.getenv("DATABASE_URL")

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "connect_args": {
        "prepare_threshold": None,
        "sslmode": "require",
    },
    "pool_pre_ping": True,
}

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255))
    role = db.Column(db.String(20), nullable=False)  # student, faculty, manager
    section = db.Column(db.String(50))
    specialization = db.Column(db.String(150))
    status = db.Column(db.String(20), default="active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return bool(self.password_hash) and check_password_hash(self.password_hash, password)


class Scenario(db.Model):
    __tablename__ = "scenarios"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    scenario_type = db.Column(db.String(20), nullable=False)  # chat or quiz
    category = db.Column(db.String(100), nullable=False)
    patient_name = db.Column(db.String(150), nullable=False)
    patient_age = db.Column(db.String(50))
    emotional_state = db.Column(db.String(100))
    clinical_context = db.Column(db.Text)
    opening_statement = db.Column(db.Text)
    difficulty = db.Column(db.String(20), default="Beginner")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ScenarioChoice(db.Model):
    __tablename__ = "scenario_choices"
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey("scenarios.id"), nullable=False)
    choice_text = db.Column(db.Text, nullable=False)
    is_best_answer = db.Column(db.Boolean, default=False)
    classification = db.Column(db.String(30), default="therapeutic")
    rationale = db.Column(db.Text)


class ChatSession(db.Model):
    __tablename__ = "chat_sessions"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    scenario_id = db.Column(db.Integer, db.ForeignKey("scenarios.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="in_progress")
    overall_score = db.Column(db.Float)
    feedback_summary = db.Column(db.Text)


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id = db.Column(db.Integer, primary_key=True)
    chat_session_id = db.Column(db.Integer, db.ForeignKey("chat_sessions.id"), nullable=False)
    sender = db.Column(db.String(20), nullable=False)  # student or patient_ai
    message_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Evaluation(db.Model):
    __tablename__ = "evaluations"
    id = db.Column(db.Integer, primary_key=True)
    chat_session_id = db.Column(db.Integer, db.ForeignKey("chat_sessions.id"), nullable=False, unique=True)
    empathy_score = db.Column(db.Float)
    open_ended_score = db.Column(db.Float)
    active_listening_score = db.Column(db.Float)
    professionalism_score = db.Column(db.Float)
    barrier_avoidance_score = db.Column(db.Float)
    overall_score = db.Column(db.Float)
    strengths = db.Column(db.Text)
    improvements = db.Column(db.Text)
    improved_response_examples = db.Column(db.Text)
    evaluated_at = db.Column(db.DateTime, default=datetime.utcnow)


class DecisionAttempt(db.Model):
    __tablename__ = "decision_attempts"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    scenario_id = db.Column(db.Integer, db.ForeignKey("scenarios.id"), nullable=False)
    selected_choice_id = db.Column(db.Integer, db.ForeignKey("scenario_choices.id"), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    score = db.Column(db.Float, default=0)
    rationale = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SystemSetting(db.Model):
    __tablename__ = "system_settings"
    id = db.Column(db.Integer, primary_key=True)
    site_name = db.Column(db.String(150), default="TheraComm AI")


THERAPEUTIC_MARKERS = [
    "can you tell me more",
    "i understand",
    "i hear",
    "what worries you",
    "it sounds like",
    "how are you feeling",
    "tell me more",
    "i can see",
    "that sounds",
    "what concerns you",
]
NONTHERAPEUTIC_MARKERS = [
    "don't worry",
    "dont worry",
    "you should",
    "calm down",
    "everything will be fine",
    "at least",
    "why didn't you",
    "just",
]


def normalize_email(email):
    return (email or "").strip().lower()


def parse_json_from_text(text):
    try:
        return json.loads(text)
    except Exception:
        start, end = text.find("{"), text.rfind("}")
        return json.loads(text[start:end+1])


def fallback_patient_reply(scenario, student_message, turn_count):
    msg = (student_message or "").lower()
    if any(x in msg for x in ["tell me more", "what worries", "how are you feeling", "can you share"]):
        return f"I feel really nervous. {scenario.patient_name if scenario.patient_name else 'I'} keep thinking something bad might happen."
    if any(x in msg for x in ["don't worry", "dont worry", "calm down"]):
        return "I know you're trying to help, but I still feel worried and not fully understood."
    canned = [
        "I'm still anxious and I don't know what to expect.",
        "I just want someone to explain things clearly.",
        "I'm scared because this feels overwhelming.",
        "I want to know if what I'm feeling is normal.",
    ]
    return canned[turn_count % len(canned)]


def analyze_chat_fallback(messages):
    student_msgs = [m.message_text for m in messages if m.sender == "student"]
    joined = " ".join(student_msgs).lower()
    empathy = min(25, 10 + sum(1 for m in THERAPEUTIC_MARKERS if m in joined) * 3)
    open_q = min(20, 8 + joined.count("?") * 3)
    active = min(20, 8 + sum(1 for m in ["tell me more", "it sounds like", "i hear", "i understand"] if m in joined) * 4)
    prof = 18 if student_msgs else 0
    penalty = sum(1 for m in NONTHERAPEUTIC_MARKERS if m in joined)
    barrier = max(10, 15 - penalty * 2)
    overall = round(empathy + open_q + active + prof + barrier, 2)
    strengths = []
    improvements = []
    if "?" in joined:
        strengths.append("Used questions to explore the patient's concern.")
    if any(m in joined for m in ["i understand", "i can see", "it sounds like"]):
        strengths.append("Showed empathy or emotional acknowledgment.")
    if not strengths:
        strengths.append("Maintained engagement with the patient conversation.")
    if penalty:
        improvements.append("Avoid false reassurance or directive phrasing.")
    if joined.count("?") == 0:
        improvements.append("Use more open-ended questions.")
    if not any(m in joined for m in ["i understand", "i can see", "it sounds like", "what worries you"]):
        improvements.append("Add more validating statements to show empathy.")
    if not improvements:
        improvements.append("Keep refining therapeutic wording for greater depth.")
    examples = [
        "I can see that you're feeling worried. Can you tell me more about what concerns you most right now?",
        "It sounds like this situation feels overwhelming. What part of it is hardest for you at the moment?",
    ]
    return {
        "empathy_score": empathy,
        "open_ended_score": open_q,
        "active_listening_score": active,
        "professionalism_score": prof,
        "barrier_avoidance_score": barrier,
        "overall_score": overall,
        "strengths": strengths,
        "improvements": improvements,
        "examples": examples,
        "feedback_summary": "The conversation shows developing therapeutic communication skills with areas for refinement in empathy, exploration, and avoidance of non-therapeutic phrasing.",
    }


def openai_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return None
    return OpenAI(api_key=api_key)


def generate_patient_reply(scenario, transcript, student_message):
    client = openai_client()
    if client is None:
        return fallback_patient_reply(scenario, student_message, len(transcript))
    prompt = f"""
You are a virtual patient in a nursing therapeutic communication training system.
Stay in character. Respond naturally, briefly, and emotionally as the patient.
Do not explain or teach. React as a patient would.

Scenario:
Title: {scenario.title}
Patient: {scenario.patient_name}, age {scenario.patient_age}
Emotion: {scenario.emotional_state}
Clinical context: {scenario.clinical_context}
Opening statement: {scenario.opening_statement}

Transcript so far:
{json.dumps(transcript, ensure_ascii=False)}

Latest student message:
{student_message}
"""
    try:
        resp = client.responses.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
            input=prompt,
            temperature=0.7,
        )
        return resp.output_text.strip()
    except Exception:
        return fallback_patient_reply(scenario, student_message, len(transcript))


def evaluate_chat(messages):
    client = openai_client()
    transcript = [{"sender": m.sender, "text": m.message_text} for m in messages]
    if client is None:
        return analyze_chat_fallback(messages)
    prompt = f"""
You are evaluating a nursing student's therapeutic communication.
Analyze the transcript and return ONLY valid JSON with keys:
empathy_score, open_ended_score, active_listening_score, professionalism_score, barrier_avoidance_score, overall_score, strengths, improvements, examples, feedback_summary.
Scores should total 100.
Transcript:
{json.dumps(transcript, ensure_ascii=False)}
"""
    try:
        resp = client.responses.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
            input=prompt,
            temperature=0.2,
        )
        return parse_json_from_text(resp.output_text)
    except Exception:
        return analyze_chat_fallback(messages)


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
    database_url = os.environ.get("DATABASE_URL", "sqlite:///theracomm.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if "supabase.co" in database_url and "sslmode=" not in database_url:
        database_url += ("&" if "?" in database_url else "?") + "sslmode=require"
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {
            "prepare_threshold": None,
            "sslmode": "require",
        },
        "pool_pre_ping": True,
    }
    db.init_app(app)

    def login_required(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in first.", "warning")
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return wrapper

    def role_required(*roles):
        def deco(f):
            @wraps(f)
            def wrapper(*args, **kwargs):
                if session.get("user_role") not in roles:
                    flash("Unauthorized access.", "danger")
                    return redirect(url_for("home"))
                return f(*args, **kwargs)
            return wrapper
        return deco

    with app.app_context():
        db.create_all()
        if not SystemSetting.query.first():
            db.session.add(SystemSetting(site_name="TheraComm AI"))
        demos = [
            ("System Manager", "manager@theracomm.ai", "manager", "Manager123!"),
            ("Faculty Reviewer", "faculty@theracomm.ai", "faculty", "Faculty123!"),
            ("Student User", "student@theracomm.ai", "student", "Student123!"),
        ]
        for full_name, email, role, pw in demos:
            if not User.query.filter_by(email=email).first():
                u = User(full_name=full_name, email=email, role=role, status="active")
                if role == "student":
                    u.section = "BSN 4A"
                if role == "faculty":
                    u.specialization = "Nursing Education"
                u.set_password(pw)
                db.session.add(u)
        if Scenario.query.count() == 0:
            s1 = Scenario(
                title="Anxious Mother in Pediatric Ward",
                scenario_type="chat",
                category="Pediatrics",
                patient_name="Mrs. Santos",
                patient_age="32",
                emotional_state="Anxious",
                clinical_context="Her child has fever and is crying in the pediatric ward.",
                opening_statement="Nurse, I'm really worried about my child. Why is the fever not going down yet?",
                difficulty="Beginner",
            )
            s2 = Scenario(
                title="Preoperative Anxiety",
                scenario_type="quiz",
                category="Medical-Surgical",
                patient_name="Mr. Reyes",
                patient_age="46",
                emotional_state="Fearful",
                clinical_context="The patient is scheduled for surgery and expresses fear.",
                opening_statement="I don't think I can do this operation.",
                difficulty="Beginner",
            )
            s3 = Scenario(
                title="Adolescent Refusing Treatment",
                scenario_type="chat",
                category="Adolescent Health",
                patient_name="Janelle",
                patient_age="17",
                emotional_state="Defensive",
                clinical_context="Adolescent patient is withdrawn and hesitant to cooperate.",
                opening_statement="I don't want to talk about it. I just want to go home.",
                difficulty="Intermediate",
            )
            db.session.add_all([s1, s2, s3])
            db.session.flush()
            db.session.add_all([
                ScenarioChoice(scenario_id=s2.id, choice_text="Don't worry, everything will be fine.", is_best_answer=False, classification="non_therapeutic", rationale="This offers false reassurance and does not explore the patient's fear."),
                ScenarioChoice(scenario_id=s2.id, choice_text="Can you tell me what concerns you most about the surgery?", is_best_answer=True, classification="therapeutic", rationale="This is open-ended, explores feelings, and encourages expression of concern."),
                ScenarioChoice(scenario_id=s2.id, choice_text="You need to be strong for your family.", is_best_answer=False, classification="non_therapeutic", rationale="This is advising and may pressure the patient instead of validating feelings."),
                ScenarioChoice(scenario_id=s2.id, choice_text="Try not to think too much about it.", is_best_answer=False, classification="non_therapeutic", rationale="This dismisses the patient's concern and blocks communication."),
            ])
        db.session.commit()

    @app.context_processor
    def inject_globals():
        return {
            "settings": SystemSetting.query.first(),
            "session_user_name": session.get("user_name"),
            "session_user_role": session.get("user_role"),
        }

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

    @app.route("/api/health")
    def api_health():
        return jsonify({"status": "ok", "message": "TheraComm AI backend is running"})

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            user = User.query.filter_by(email=normalize_email(request.form.get("email")), status="active").first()
            if user and user.check_password(request.form.get("password", "")):
                session["user_id"] = user.id
                session["user_name"] = user.full_name
                session["user_role"] = user.role
                flash("Login successful.", "success")
                return redirect(url_for("home"))
            flash("Invalid credentials.", "danger")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("Logged out.", "info")
        return redirect(url_for("login"))

    @app.route("/student")
    @login_required
    @role_required("student")
    def student_dashboard():
        chat_sessions = ChatSession.query.filter_by(student_id=session["user_id"]).order_by(ChatSession.started_at.desc()).all()
        decision_attempts = DecisionAttempt.query.filter_by(student_id=session["user_id"]).order_by(DecisionAttempt.created_at.desc()).all()
        avg_chat = round(sum((s.overall_score or 0) for s in chat_sessions)/len(chat_sessions), 2) if chat_sessions else 0
        avg_quiz = round(sum((a.score or 0) for a in decision_attempts)/len(decision_attempts), 2) if decision_attempts else 0
        return render_template(
            "student/dashboard.html",
            chat_sessions=chat_sessions[:5],
            decision_attempts=decision_attempts[:5],
            avg_chat=avg_chat,
            avg_quiz=avg_quiz,
            scenarios=Scenario.query.order_by(Scenario.id.asc()).all(),
        )

    @app.route("/student/simulator")
    @login_required
    @role_required("student")
    def student_simulator_list():
        scenarios = Scenario.query.filter_by(scenario_type="chat").order_by(Scenario.id.asc()).all()
        return render_template("student/simulator_list.html", scenarios=scenarios)

    @app.route("/student/simulator/<int:scenario_id>", methods=["GET", "POST"])
    @login_required
    @role_required("student")
    def student_simulator_chat(scenario_id):
        scenario = db.session.get(Scenario, scenario_id)
        if not scenario or scenario.scenario_type != "chat":
            flash("Scenario not found.", "danger")
            return redirect(url_for("student_simulator_list"))

        chat_session = ChatSession.query.filter_by(student_id=session["user_id"], scenario_id=scenario_id, status="in_progress").order_by(ChatSession.started_at.desc()).first()
        if not chat_session:
            chat_session = ChatSession(student_id=session["user_id"], scenario_id=scenario_id, status="in_progress")
            db.session.add(chat_session)
            db.session.flush()
            db.session.add(ChatMessage(chat_session_id=chat_session.id, sender="patient_ai", message_text=scenario.opening_statement))
            db.session.commit()

        if request.method == "POST":
            msg = request.form.get("message", "").strip()
            action = request.form.get("action", "send")
            if action == "end":
                return redirect(url_for("student_finish_chat", chat_session_id=chat_session.id))
            if msg:
                db.session.add(ChatMessage(chat_session_id=chat_session.id, sender="student", message_text=msg))
                db.session.flush()
                transcript = [{"sender": m.sender, "text": m.message_text} for m in ChatMessage.query.filter_by(chat_session_id=chat_session.id).order_by(ChatMessage.created_at.asc()).all()]
                reply = generate_patient_reply(scenario, transcript, msg)
                db.session.add(ChatMessage(chat_session_id=chat_session.id, sender="patient_ai", message_text=reply))
                db.session.commit()
            else:
                flash("Please enter a message.", "warning")
            return redirect(url_for("student_simulator_chat", scenario_id=scenario_id))

        messages = ChatMessage.query.filter_by(chat_session_id=chat_session.id).order_by(ChatMessage.created_at.asc()).all()
        return render_template("student/simulator_chat.html", scenario=scenario, chat_session=chat_session, messages=messages)

    @app.route("/student/chat/<int:chat_session_id>/finish")
    @login_required
    @role_required("student")
    def student_finish_chat(chat_session_id):
        chat_session = db.session.get(ChatSession, chat_session_id)
        if not chat_session or chat_session.student_id != session["user_id"]:
            flash("Session not found.", "danger")
            return redirect(url_for("student_dashboard"))
        messages = ChatMessage.query.filter_by(chat_session_id=chat_session.id).order_by(ChatMessage.created_at.asc()).all()
        result = evaluate_chat(messages)
        evaluation = Evaluation.query.filter_by(chat_session_id=chat_session.id).first()
        if not evaluation:
            evaluation = Evaluation(chat_session_id=chat_session.id)
            db.session.add(evaluation)
        evaluation.empathy_score = float(result.get("empathy_score", 0))
        evaluation.open_ended_score = float(result.get("open_ended_score", 0))
        evaluation.active_listening_score = float(result.get("active_listening_score", 0))
        evaluation.professionalism_score = float(result.get("professionalism_score", 0))
        evaluation.barrier_avoidance_score = float(result.get("barrier_avoidance_score", 0))
        evaluation.overall_score = float(result.get("overall_score", 0))
        evaluation.strengths = json.dumps(result.get("strengths", []))
        evaluation.improvements = json.dumps(result.get("improvements", []))
        evaluation.improved_response_examples = json.dumps(result.get("examples", []))
        chat_session.overall_score = evaluation.overall_score
        chat_session.feedback_summary = result.get("feedback_summary")
        chat_session.status = "completed"
        chat_session.ended_at = datetime.utcnow()
        db.session.commit()
        flash("Session evaluated successfully.", "success")
        return redirect(url_for("student_chat_result", chat_session_id=chat_session.id))

    @app.route("/student/chat/<int:chat_session_id>/result")
    @login_required
    @role_required("student")
    def student_chat_result(chat_session_id):
        chat_session = db.session.get(ChatSession, chat_session_id)
        if not chat_session or chat_session.student_id != session["user_id"]:
            flash("Result not found.", "danger")
            return redirect(url_for("student_dashboard"))
        evaluation = Evaluation.query.filter_by(chat_session_id=chat_session.id).first()
        messages = ChatMessage.query.filter_by(chat_session_id=chat_session.id).order_by(ChatMessage.created_at.asc()).all()
        return render_template(
            "student/chat_result.html",
            chat_session=chat_session,
            evaluation=evaluation,
            strengths=json.loads(evaluation.strengths or "[]") if evaluation else [],
            improvements=json.loads(evaluation.improvements or "[]") if evaluation else [],
            examples=json.loads(evaluation.improved_response_examples or "[]") if evaluation else [],
            messages=messages,
            scenario=db.session.get(Scenario, chat_session.scenario_id),
        )

    @app.route("/student/trainer")
    @login_required
    @role_required("student")
    def student_trainer_list():
        scenarios = Scenario.query.filter_by(scenario_type="quiz").order_by(Scenario.id.asc()).all()
        return render_template("student/trainer_list.html", scenarios=scenarios)

    @app.route("/student/trainer/<int:scenario_id>", methods=["GET", "POST"])
    @login_required
    @role_required("student")
    def student_trainer_detail(scenario_id):
        scenario = db.session.get(Scenario, scenario_id)
        if not scenario or scenario.scenario_type != "quiz":
            flash("Scenario not found.", "danger")
            return redirect(url_for("student_trainer_list"))
        choices = ScenarioChoice.query.filter_by(scenario_id=scenario.id).order_by(ScenarioChoice.id.asc()).all()
        latest_attempt = DecisionAttempt.query.filter_by(student_id=session["user_id"], scenario_id=scenario.id).order_by(DecisionAttempt.created_at.desc()).first()
        if request.method == "POST":
            choice_id = int(request.form.get("choice_id"))
            selected = db.session.get(ScenarioChoice, choice_id)
            is_correct = bool(selected and selected.is_best_answer)
            score = 100.0 if is_correct else 60.0
            attempt = DecisionAttempt(
                student_id=session["user_id"],
                scenario_id=scenario.id,
                selected_choice_id=choice_id,
                is_correct=is_correct,
                score=score,
                rationale=selected.rationale if selected else "",
            )
            db.session.add(attempt)
            db.session.commit()
            flash("Scenario submitted.", "success")
            return redirect(url_for("student_trainer_result", attempt_id=attempt.id))
        return render_template("student/trainer_detail.html", scenario=scenario, choices=choices, latest_attempt=latest_attempt)

    @app.route("/student/trainer/result/<int:attempt_id>")
    @login_required
    @role_required("student")
    def student_trainer_result(attempt_id):
        attempt = db.session.get(DecisionAttempt, attempt_id)
        if not attempt or attempt.student_id != session["user_id"]:
            flash("Attempt not found.", "danger")
            return redirect(url_for("student_trainer_list"))
        scenario = db.session.get(Scenario, attempt.scenario_id)
        selected = db.session.get(ScenarioChoice, attempt.selected_choice_id)
        choices = ScenarioChoice.query.filter_by(scenario_id=scenario.id).order_by(ScenarioChoice.id.asc()).all()
        best = next((c for c in choices if c.is_best_answer), None)
        return render_template("student/trainer_result.html", attempt=attempt, scenario=scenario, selected=selected, choices=choices, best=best)

    @app.route("/faculty")
    @login_required
    @role_required("faculty")
    def faculty_dashboard():
        total_chat = ChatSession.query.filter_by(status="completed").count()
        total_quiz = DecisionAttempt.query.count()
        avg_chat = db.session.query(db.func.avg(ChatSession.overall_score)).scalar() or 0
        avg_quiz = db.session.query(db.func.avg(DecisionAttempt.score)).scalar() or 0
        low_empathy = Evaluation.query.filter(Evaluation.empathy_score < 18).count()
        return render_template("faculty/dashboard.html", total_chat=total_chat, total_quiz=total_quiz, avg_chat=round(avg_chat, 2), avg_quiz=round(avg_quiz, 2), low_empathy=low_empathy)

    @app.route("/faculty/sessions")
    @login_required
    @role_required("faculty")
    def faculty_sessions():
        sessions = ChatSession.query.order_by(ChatSession.started_at.desc()).all()
        return render_template("faculty/sessions.html", sessions=sessions, User=User, Scenario=Scenario)

    @app.route("/faculty/sessions/<int:chat_session_id>")
    @login_required
    @role_required("faculty")
    def faculty_session_detail(chat_session_id):
        chat_session = db.session.get(ChatSession, chat_session_id)
        if not chat_session:
            flash("Session not found.", "danger")
            return redirect(url_for("faculty_sessions"))
        evaluation = Evaluation.query.filter_by(chat_session_id=chat_session.id).first()
        messages = ChatMessage.query.filter_by(chat_session_id=chat_session.id).order_by(ChatMessage.created_at.asc()).all()
        return render_template(
            "faculty/session_detail.html",
            chat_session=chat_session,
            student=db.session.get(User, chat_session.student_id),
            scenario=db.session.get(Scenario, chat_session.scenario_id),
            evaluation=evaluation,
            strengths=json.loads(evaluation.strengths or "[]") if evaluation else [],
            improvements=json.loads(evaluation.improvements or "[]") if evaluation else [],
            examples=json.loads(evaluation.improved_response_examples or "[]") if evaluation else [],
            messages=messages,
        )

    @app.route("/faculty/trainer-attempts")
    @login_required
    @role_required("faculty")
    def faculty_trainer_attempts():
        attempts = DecisionAttempt.query.order_by(DecisionAttempt.created_at.desc()).all()
        return render_template("faculty/trainer_attempts.html", attempts=attempts, User=User, Scenario=Scenario, ScenarioChoice=ScenarioChoice)

    @app.route("/faculty/curriculum-insights")
    @login_required
    @role_required("faculty")
    def faculty_curriculum_insights():
        evals = Evaluation.query.all()
        avg_by_criterion = []
        if evals:
            avg_by_criterion = [
                {"criterion": "Empathy", "avg_score": round(sum(e.empathy_score or 0 for e in evals)/len(evals), 2)},
                {"criterion": "Open-ended Questions", "avg_score": round(sum(e.open_ended_score or 0 for e in evals)/len(evals), 2)},
                {"criterion": "Active Listening", "avg_score": round(sum(e.active_listening_score or 0 for e in evals)/len(evals), 2)},
                {"criterion": "Professionalism", "avg_score": round(sum(e.professionalism_score or 0 for e in evals)/len(evals), 2)},
                {"criterion": "Barrier Avoidance", "avg_score": round(sum(e.barrier_avoidance_score or 0 for e in evals)/len(evals), 2)},
            ]
            avg_by_criterion.sort(key=lambda x: x["avg_score"])
        tag_counts = {
            "empathy reinforcement": sum(1 for e in evals if (e.empathy_score or 0) < 18),
            "open-ended questioning": sum(1 for e in evals if (e.open_ended_score or 0) < 14),
            "active listening": sum(1 for e in evals if (e.active_listening_score or 0) < 14),
            "avoid false reassurance": sum(1 for e in evals if (e.barrier_avoidance_score or 0) < 12),
        }
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
        narrative = "Students most frequently need reinforcement in: " + ", ".join([t[0] for t in top_tags if t[1] > 0]) if any(v > 0 for v in tag_counts.values()) else "No strong remediation trend yet."
        return render_template("faculty/curriculum_insights.html", avg_by_criterion=avg_by_criterion, top_tags=top_tags, narrative=narrative)

    @app.route("/faculty/reports.csv")
    @login_required
    @role_required("faculty")
    def faculty_reports_csv():
        rows = [["Type", "Student", "Scenario", "Score", "Status", "Created At"]]
        for s in ChatSession.query.order_by(ChatSession.started_at.desc()).all():
            stu = db.session.get(User, s.student_id)
            sc = db.session.get(Scenario, s.scenario_id)
            rows.append(["Chat OSCE", stu.full_name if stu else "Unknown", sc.title if sc else "Unknown", s.overall_score or "", s.status, s.started_at.strftime("%Y-%m-%d %H:%M")])
        for a in DecisionAttempt.query.order_by(DecisionAttempt.created_at.desc()).all():
            stu = db.session.get(User, a.student_id)
            sc = db.session.get(Scenario, a.scenario_id)
            rows.append(["Decision Trainer", stu.full_name if stu else "Unknown", sc.title if sc else "Unknown", a.score or "", "submitted", a.created_at.strftime("%Y-%m-%d %H:%M")])
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerows(rows)
        mem = io.BytesIO(buf.getvalue().encode("utf-8"))
        mem.seek(0)
        return send_file(mem, mimetype="text/csv", as_attachment=True, download_name="theracomm_report.csv")

    @app.route("/manager")
    @login_required
    @role_required("manager")
    def manager_dashboard():
        return render_template(
            "manager/dashboard.html",
            total_users=User.query.count(),
            total_students=User.query.filter_by(role="student").count(),
            total_faculty=User.query.filter_by(role="faculty").count(),
            total_chat=ChatSession.query.count(),
            total_attempts=DecisionAttempt.query.count(),
        )

    @app.route("/manager/users")
    @login_required
    @role_required("manager")
    def manager_users():
        return render_template("manager/users.html", users=User.query.order_by(User.role.asc(), User.full_name.asc()).all())

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
