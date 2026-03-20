from ..models import User, Scenario, ScenarioChoice


def seed_database(db):
    if User.query.count() == 0:
        faculty = User(full_name='Demo Faculty', email='faculty@theracomm.ai', role='faculty')
        faculty.set_password('faculty123')
        student = User(full_name='Demo Student', email='student@theracomm.ai', role='student', year_level='4', section='A')
        student.set_password('student123')
        db.session.add_all([faculty, student])
        db.session.commit()

    if Scenario.query.count() > 0:
        return

    chat_scenarios = [
        Scenario(
            title='Anxious Mother in Pediatric Ward',
            category='Pediatric Nursing',
            patient_name='Mrs. Santos',
            patient_age=32,
            clinical_context='Mother of a 5-year-old child admitted for high fever and dehydration.',
            emotional_state='anxious',
            chief_concern='She is worried her child might get worse overnight.',
            difficulty_level='basic',
            opening_statement='Nurse, I am really worried. My child keeps crying and I am scared something bad might happen.',
            scenario_type='chat',
        ),
        Scenario(
            title='Preoperative Adolescent Patient',
            category='Medical-Surgical Nursing',
            patient_name='Mark',
            patient_age=16,
            clinical_context='Teenage patient scheduled for appendectomy.',
            emotional_state='fearful',
            chief_concern='He is afraid of surgery and does not want to talk much.',
            difficulty_level='intermediate',
            opening_statement='I do not want this operation. What if I do not wake up?',
            scenario_type='chat',
        ),
    ]

    decision_scenario = Scenario(
        title='Postoperative Pain Concern',
        category='Clinical Communication',
        patient_name='Mr. Reyes',
        patient_age=54,
        clinical_context='Adult patient six hours after abdominal surgery reporting pain and distress.',
        emotional_state='distressed',
        chief_concern='He feels that nobody is listening to his pain complaint.',
        difficulty_level='basic',
        opening_statement='Nurse, the pain is getting worse and I feel like no one is listening to me.',
        scenario_type='decision',
    )

    db.session.add_all(chat_scenarios + [decision_scenario])
    db.session.commit()

    choices = [
        ScenarioChoice(
            scenario_id=decision_scenario.id,
            choice_text='Do not worry, pain is expected after surgery.',
            is_best_answer=False,
            rationale='This minimizes the patient’s concern and offers false reassurance.',
            classification='non_therapeutic',
        ),
        ScenarioChoice(
            scenario_id=decision_scenario.id,
            choice_text='I can see that this is really uncomfortable. Can you tell me more about the pain you are feeling right now?',
            is_best_answer=True,
            rationale='This validates the patient’s distress and uses exploration to gather more assessment data.',
            classification='therapeutic',
        ),
        ScenarioChoice(
            scenario_id=decision_scenario.id,
            choice_text='Please be patient. The doctor will come later.',
            is_best_answer=False,
            rationale='This delays engagement and does not address the patient’s present emotional need.',
            classification='non_therapeutic',
        ),
        ScenarioChoice(
            scenario_id=decision_scenario.id,
            choice_text='Try to relax so the pain will not get worse.',
            is_best_answer=False,
            rationale='This shifts responsibility to the patient and does not show active listening.',
            classification='partially_therapeutic',
        ),
    ]
    db.session.add_all(choices)
    db.session.commit()
