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
    email = db.Column(db.String(120), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    section = db.Column(db.String(50))
    specialization = db.Column(db.String(100))
    status = db.Column(db.String(20), nullable=False, default="active")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    attempts = db.relationship("Attempt", backref="user", lazy=True, cascade="all, delete-orphan")
    chat_sessions = db.relationship("ChatSession", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Scenario(db.Model):
    __tablename__ = "scenarios"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    scenario_type = db.Column(db.String(30), nullable=False, default="chat")
    category = db.Column(db.String(100), nullable=False)
    patient_name = db.Column(db.String(100), nullable=False)
    patient_age = db.Column(db.Integer)
    emotional_state = db.Column(db.String(100), nullable=False)
    clinical_context = db.Column(db.Text, nullable=False)
    opening_statement = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(30), nullable=False, default="Beginner")
    learning_objective = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    choices = db.relationship("ScenarioChoice", backref="scenario", lazy=True, cascade="all, delete-orphan")
    attempts = db.relationship("Attempt", backref="scenario", lazy=True, cascade="all, delete-orphan")
    chat_sessions = db.relationship("ChatSession", backref="scenario", lazy=True, cascade="all, delete-orphan")


class ScenarioChoice(db.Model):
    __tablename__ = "scenario_choices"
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey("scenarios.id"), nullable=False)
    choice_text = db.Column(db.Text, nullable=False)
    rationale = db.Column(db.Text, nullable=False)
    is_best = db.Column(db.Boolean, nullable=False, default=False)
    classification = db.Column(db.String(30), nullable=False, default="therapeutic")


class Attempt(db.Model):
    __tablename__ = "attempts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    scenario_id = db.Column(db.Integer, db.ForeignKey("scenarios.id"), nullable=False)
    mode = db.Column(db.String(20), nullable=False, default="decision")
    selected_choice_id = db.Column(db.Integer, db.ForeignKey("scenario_choices.id"))
    student_response = db.Column(db.Text, nullable=False)
    ai_feedback = db.Column(db.Text, nullable=False)
    score = db.Column(db.Integer, nullable=False, default=0)
    empathy_score = db.Column(db.Integer, nullable=False, default=0)
    exploration_score = db.Column(db.Integer, nullable=False, default=0)
    professionalism_score = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    selected_choice = db.relationship("ScenarioChoice", lazy=True)


class ChatSession(db.Model):
    __tablename__ = "chat_sessions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    scenario_id = db.Column(db.Integer, db.ForeignKey("scenarios.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")
    final_score = db.Column(db.Integer)
    feedback_summary = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = db.relationship("ChatMessage", backref="chat_session", lazy=True, cascade="all, delete-orphan", order_by="ChatMessage.id.asc()")


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id = db.Column(db.Integer, primary_key=True)
    chat_session_id = db.Column(db.Integer, db.ForeignKey("chat_sessions.id"), nullable=False)
    sender = db.Column(db.String(20), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


def create_app():
    app = Flask(__name__)

    secret_key = os.getenv("SECRET_KEY", "dev-secret-key")
    database_url = os.getenv("DATABASE_URL", "sqlite:///theracomm_v11.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://") and "+psycopg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    app.config["SECRET_KEY"] = secret_key
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    connect_args = {}
    if database_url.startswith("postgresql+psycopg://"):
        connect_args = {"prepare_threshold": None, "sslmode": "require", "connect_timeout": 5}
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": connect_args, "pool_pre_ping": True}
    db.init_app(app)

    @app.context_processor
    def inject_globals():
        return {"current_user_name": session.get("user_name"), "current_user_role": session.get("user_role")}

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

    @app.route("/health")
    def health():
        return "ok", 200

    @app.route("/init-db")
    def init_db():
        try:
            db.create_all()
            seed_defaults()
            return "Database initialized successfully", 200
        except Exception as e:
            db.session.rollback()
            return f"Init DB error: {e}", 500

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
        flash("Logged out.", "info")
        return redirect(url_for("login"))

    @app.route("/student")
    @login_required(role="student")
    def student_dashboard():
        scenarios = Scenario.query.order_by(Scenario.id.asc()).all()
        attempts = Attempt.query.filter_by(user_id=session["user_id"]).order_by(Attempt.created_at.desc()).limit(10).all()
        chat_sessions = ChatSession.query.filter_by(user_id=session["user_id"]).order_by(ChatSession.created_at.desc()).limit(10).all()
        avg_score = round(sum(a.score for a in attempts) / len(attempts), 1) if attempts else 0
        completed_chat = [c.final_score for c in chat_sessions if c.final_score is not None]
        avg_chat = round(sum(completed_chat) / len(completed_chat), 1) if completed_chat else 0
        return render_template("student_dashboard.html", scenarios=scenarios, attempts=attempts, chat_sessions=chat_sessions, avg_score=avg_score, avg_chat=avg_chat)

    @app.route("/faculty")
    @login_required(role="faculty")
    def faculty_dashboard():
        students = User.query.filter_by(role="student").order_by(User.full_name.asc()).all()
        attempts = Attempt.query.order_by(Attempt.created_at.desc()).limit(20).all()
        chat_sessions = ChatSession.query.order_by(ChatSession.created_at.desc()).limit(20).all()

        all_attempts = Attempt.query.all()
        decision_avg = round(sum(a.score for a in all_attempts) / len(all_attempts), 1) if all_attempts else 0

        all_chats = [c.final_score for c in ChatSession.query.filter(ChatSession.final_score.isnot(None)).all()]
        chat_avg = round(sum(all_chats) / len(all_chats), 1) if all_chats else 0

        weak_counts = {"Empathy": 0, "Exploration": 0, "Professionalism": 0}
        for a in all_attempts:
            min_score = min(a.empathy_score, a.exploration_score, a.professionalism_score)
            if min_score == a.empathy_score:
                weak_counts["Empathy"] += 1
            elif min_score == a.exploration_score:
                weak_counts["Exploration"] += 1
            else:
                weak_counts["Professionalism"] += 1
        weakest_skill = max(weak_counts, key=weak_counts.get) if all_attempts else "No data yet"

        return render_template(
            "faculty_dashboard.html",
            students=students,
            attempts=attempts,
            chat_sessions=chat_sessions,
            decision_avg=decision_avg,
            chat_avg=chat_avg,
            weakest_skill=weakest_skill,
            curriculum_insight=build_curriculum_insight(all_attempts, all_chats),
        )

    @app.route("/manager")
    @login_required(role="manager")
    def manager_dashboard():
        users = User.query.order_by(User.role.asc(), User.full_name.asc()).all()
        scenarios = Scenario.query.order_by(Scenario.id.asc()).all()
        attempts = Attempt.query.count()
        chat_count = ChatSession.query.count()
        return render_template("manager_dashboard.html", users=users, scenarios=scenarios, attempts=attempts, chat_count=chat_count)

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
                user = User(full_name=full_name, email=email, role=role, section=section, specialization=specialization, status="active")
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash("User created successfully.", "success")
                return redirect(url_for("users_page"))
        users = User.query.order_by(User.role.asc(), User.full_name.asc()).all()
        return render_template("users.html", users=users)

    @app.route("/scenarios", methods=["GET", "POST"])
    @login_required(role="manager")
    def scenarios_page():
        if request.method == "POST":
            scenario = Scenario(
                title=request.form.get("title", "").strip(),
                scenario_type=request.form.get("scenario_type", "chat"),
                category=request.form.get("category", "").strip() or "General",
                patient_name=request.form.get("patient_name", "").strip() or "Patient",
                patient_age=int(request.form.get("patient_age") or 0) or None,
                emotional_state=request.form.get("emotional_state", "").strip() or "Concerned",
                clinical_context=request.form.get("clinical_context", "").strip(),
                opening_statement=request.form.get("opening_statement", "").strip(),
                difficulty=request.form.get("difficulty", "Beginner"),
                learning_objective=request.form.get("learning_objective", "").strip() or None,
            )
            if scenario.title and scenario.clinical_context and scenario.opening_statement:
                db.session.add(scenario)
                db.session.commit()
                flash("Scenario added.", "success")
                return redirect(url_for("scenarios_page"))
            flash("Title, context, and opening statement are required.", "danger")
        scenarios = Scenario.query.order_by(Scenario.id.asc()).all()
        return render_template("scenarios.html", scenarios=scenarios)

    @app.route("/scenario-decision/<int:scenario_id>", methods=["GET", "POST"])
    @login_required(role="student")
    def scenario_decision(scenario_id):
        scenario = Scenario.query.get_or_404(scenario_id)
        choices = ScenarioChoice.query.filter_by(scenario_id=scenario.id).all()
        result = None
        if request.method == "POST":
            choice_id = request.form.get("choice_id", type=int)
            choice = ScenarioChoice.query.get(choice_id) if choice_id else None
            if not choice:
                flash("Please choose a response.", "warning")
            else:
                score = 92 if choice.is_best else (70 if choice.classification == "partially_therapeutic" else 45)
                empathy, exploration, professionalism = decision_breakdown(choice)
                feedback = f"{choice.rationale} Classification: {choice.classification.replace('_', ' ').title()}."
                attempt = Attempt(
                    user_id=session["user_id"],
                    scenario_id=scenario.id,
                    mode="decision",
                    selected_choice_id=choice.id,
                    student_response=choice.choice_text,
                    ai_feedback=feedback,
                    score=score,
                    empathy_score=empathy,
                    exploration_score=exploration,
                    professionalism_score=professionalism,
                )
                db.session.add(attempt)
                db.session.commit()
                result = attempt
        return render_template("scenario_decision.html", scenario=scenario, choices=choices, result=result)

    @app.route("/chat/<int:scenario_id>")
    @login_required(role="student")
    def start_chat(scenario_id):
        scenario = Scenario.query.get_or_404(scenario_id)
        chat = ChatSession(user_id=session["user_id"], scenario_id=scenario.id, status="active")
        db.session.add(chat)
        db.session.flush()
        db.session.add(ChatMessage(chat_session_id=chat.id, sender="patient", message_text=scenario.opening_statement))
        db.session.commit()
        return redirect(url_for("chat_session", chat_id=chat.id))

    @app.route("/chat-session/<int:chat_id>", methods=["GET", "POST"])
    @login_required(role="student")
    def chat_session(chat_id):
        chat = ChatSession.query.get_or_404(chat_id)
        if chat.user_id != session.get("user_id"):
            flash("Access denied.", "danger")
            return redirect(url_for("student_dashboard"))

        if request.method == "POST" and chat.status == "active":
            student_text = request.form.get("message", "").strip()
            action = request.form.get("action", "send")
            if action == "end":
                finalize_chat(chat)
                db.session.commit()
                flash("Chat session evaluated.", "success")
                return redirect(url_for("chat_session", chat_id=chat.id))
            elif student_text:
                db.session.add(ChatMessage(chat_session_id=chat.id, sender="student", message_text=student_text))
                patient_reply = generate_patient_reply(chat.scenario, student_text, len(chat.messages))
                db.session.add(ChatMessage(chat_session_id=chat.id, sender="patient", message_text=patient_reply))
                db.session.commit()
            else:
                flash("Enter a message first.", "warning")

        return render_template("chat_session.html", chat=chat)

    @app.route("/results")
    @login_required(role="student")
    def results_page():
        attempts = Attempt.query.filter_by(user_id=session["user_id"]).order_by(Attempt.created_at.desc()).all()
        chats = ChatSession.query.filter_by(user_id=session["user_id"]).order_by(ChatSession.created_at.desc()).all()
        return render_template("results.html", attempts=attempts, chats=chats)

    return app


def seed_defaults():
    if User.query.count() == 0:
        demo_users = [
            ("System Manager", "manager@theracomm.ai", "Manager123!", "manager", None, "Program Management"),
            ("Faculty Evaluator", "faculty@theracomm.ai", "Faculty123!", "faculty", "BSN 4A", "Therapeutic Communication"),
            ("Student Demo", "student@theracomm.ai", "Student123!", "student", "BSN 4A", None),
        ]
        for full_name, email, password, role, section, specialization in demo_users:
            user = User(full_name=full_name, email=email, role=role, section=section, specialization=specialization, status="active")
            user.set_password(password)
            db.session.add(user)
        db.session.commit()

    if Scenario.query.count() == 0:
        s1 = Scenario(
            title="Anxious Mother of a Febrile Child",
            scenario_type="chat",
            category="Pediatric Nursing",
            patient_name="Mrs. Santos",
            patient_age=32,
            emotional_state="Anxious",
            clinical_context="A mother is worried because her 4-year-old child has fever and keeps crying in the pediatric ward.",
            opening_statement="Nurse, I am really scared. My child keeps crying and the fever is not going away.",
            difficulty="Beginner",
            learning_objective="Demonstrate empathy, validation, and open-ended questioning.",
        )
        s2 = Scenario(
            title="Preoperative Fear",
            scenario_type="decision",
            category="Medical-Surgical Nursing",
            patient_name="Mr. Reyes",
            patient_age=54,
            emotional_state="Fearful",
            clinical_context="An adult patient is scheduled for surgery tomorrow and is expressing fear and uncertainty.",
            opening_statement="I do not think I can go through with this operation. What if something goes wrong?",
            difficulty="Intermediate",
            learning_objective="Respond therapeutically to fear and encourage verbalization of concerns.",
        )
        s3 = Scenario(
            title="Adolescent Refusing Treatment",
            scenario_type="chat",
            category="Adolescent Health",
            patient_name="Jamie",
            patient_age=16,
            emotional_state="Defensive",
            clinical_context="An adolescent patient is upset and does not want to cooperate with the prescribed care plan.",
            opening_statement="I do not want this anymore. Everyone keeps telling me what to do.",
            difficulty="Intermediate",
            learning_objective="Use nonjudgmental communication and encourage shared decision-making.",
        )
        db.session.add_all([s1, s2, s3])
        db.session.commit()

        choices = [
            ScenarioChoice(scenario_id=s2.id, choice_text="Don't worry, everything will be fine.", rationale="This gives false reassurance and may shut down further sharing.", is_best=False, classification="non_therapeutic"),
            ScenarioChoice(scenario_id=s2.id, choice_text="Can you tell me what concerns you most about the surgery?", rationale="This invites the patient to express feelings and uses an open-ended therapeutic approach.", is_best=True, classification="therapeutic"),
            ScenarioChoice(scenario_id=s2.id, choice_text="You need the operation, so try not to think negatively.", rationale="This is directive and dismisses the patient's emotional experience.", is_best=False, classification="non_therapeutic"),
            ScenarioChoice(scenario_id=s2.id, choice_text="It is normal to feel scared before surgery. Let's talk about what worries you.", rationale="This is validating and therapeutic, though slightly less exploratory than the best answer.", is_best=False, classification="partially_therapeutic"),
        ]
        db.session.add_all(choices)
        db.session.commit()


def decision_breakdown(choice):
    if choice.is_best:
        return 32, 30, 30
    if choice.classification == "partially_therapeutic":
        return 26, 20, 24
    return 12, 10, 23


def generate_patient_reply(scenario, student_text, turn_index):
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key and OpenAI is not None:
        try:
            client = OpenAI(api_key=api_key)
            prompt = f"""
You are roleplaying as a patient in a nursing therapeutic communication training app.
Stay in character. Keep reply to 1-3 sentences.
Patient name: {scenario.patient_name}
Age: {scenario.patient_age}
Emotional state: {scenario.emotional_state}
Context: {scenario.clinical_context}
Student message: {student_text}
Conversation turn: {turn_index}
"""
            response = client.responses.create(model="gpt-4.1-mini", input=prompt)
            return response.output_text.strip()
        except Exception:
            pass

    text = student_text.lower()
    if any(k in text for k in ["tell me", "what worries", "how are you", "more about"]):
        if scenario.emotional_state.lower() == "anxious":
            return "I am scared the fever means something serious. I feel helpless seeing my child like this."
        if scenario.emotional_state.lower() == "defensive":
            return "I am tired of people deciding everything for me. No one even asks what I want."
    if any(k in text for k in ["understand", "sorry", "can see", "feel"]):
        return "Thank you for listening. I just need someone to explain things and hear me out."
    if any(k in text for k in ["don't worry", "calm down", "it will be fine"]):
        return "That does not really make me feel better. I am still worried."
    return "I still feel overwhelmed. Can you stay with me and help me understand what is happening?"


def evaluate_chat_messages(chat):
    student_messages = [m.message_text for m in chat.messages if m.sender == "student"]
    joined = " ".join(student_messages).lower()
    score = 50
    empathy = 15
    exploration = 15
    professionalism = 20
    suggestions = []
    strengths = []

    if any(word in joined for word in ["understand", "sorry", "can see", "feeling", "worried"]):
        empathy += 15
        score += 15
        strengths.append("You acknowledged the patient's feelings.")
    else:
        suggestions.append("Use more empathic validation.")

    if any(word in joined for word in ["can you tell me", "what", "how", "more about"]):
        exploration += 15
        score += 15
        strengths.append("You used exploratory questioning.")
    else:
        suggestions.append("Ask open-ended questions to explore concerns.")

    if not any(word in joined for word in ["don't worry", "calm down", "stop", "just"]):
        professionalism += 10
        score += 10
        strengths.append("You avoided obvious non-therapeutic barriers.")
    else:
        professionalism -= 5
        score -= 10
        suggestions.append("Avoid false reassurance or dismissive phrasing.")

    if len(student_messages) >= 3:
        score += 10
        strengths.append("You sustained a multi-turn therapeutic interaction.")
    else:
        suggestions.append("Continue the conversation long enough to assess concerns more fully.")

    score = max(0, min(100, score))
    summary = f"Score: {score}/100. Strengths: {' '.join(strengths) if strengths else 'Developing communication.'} Suggestions: {' '.join(suggestions) if suggestions else 'Keep practicing reflective therapeutic responses.'}"
    return score, summary


def finalize_chat(chat):
    score, summary = evaluate_chat_messages(chat)
    chat.status = "completed"
    chat.final_score = score
    chat.feedback_summary = summary


def build_curriculum_insight(attempts, chat_scores):
    if not attempts and not chat_scores:
        return "No performance data yet. Encourage students to complete both decision and chat activities."
    low_empathy = sum(1 for a in attempts if a.empathy_score < 20)
    low_explore = sum(1 for a in attempts if a.exploration_score < 20)
    if low_empathy >= low_explore:
        return "Most students need reinforcement in empathy and validation. Consider more modeling of reflective statements and patient-feeling acknowledgment."
    return "Students show greater difficulty with exploration. Consider adding drills on open-ended questions and follow-up probing."


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
