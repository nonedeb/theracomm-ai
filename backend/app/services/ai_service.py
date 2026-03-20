import os
from statistics import mean

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


THERAPEUTIC_KEYWORDS = ['feel', 'can you tell me', 'more about', 'worried', 'understand', 'help', 'concern', 'what']
NON_THERAPEUTIC_KEYWORDS = ['do not worry', "don't worry", 'calm down', 'you should', 'be positive', 'nothing to worry']


def _client():
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key and OpenAI is not None:
        return OpenAI(api_key=api_key)
    return None


def generate_patient_reply(scenario, history, student_message):
    client = _client()
    if client:
        system_prompt = f"""
You are a virtual patient in a nursing therapeutic communication training system.
Stay in character. Be realistic, concise, and emotional.
Scenario:
Patient name: {scenario.patient_name}
Age: {scenario.patient_age}
Clinical context: {scenario.clinical_context}
Emotional state: {scenario.emotional_state}
Main concern: {scenario.chief_concern}
Opening statement: {scenario.opening_statement}
"""
        messages = [{'role': 'system', 'content': system_prompt}]
        for item in history[-8:]:
            role = 'assistant' if item['sender'] == 'patient_ai' else 'user'
            messages.append({'role': role, 'content': item['message_text']})
        messages.append({'role': 'user', 'content': student_message})
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=messages,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()

    lowered = student_message.lower()
    if any(k in lowered for k in NON_THERAPEUTIC_KEYWORDS):
        return 'That does not really make me feel better. I am still scared and I need someone to listen to me.'
    if 'pain' in scenario.chief_concern.lower():
        return 'It feels sharp and heavy at the same time. I am worried it means something is wrong.'
    if 'child' in scenario.clinical_context.lower():
        return 'I just want to know if my child is safe. I feel helpless seeing my child like this.'
    return 'I am still nervous. I do not know what will happen, and that makes me afraid.'


def evaluate_conversation(messages):
    student_messages = [m['message_text'] for m in messages if m['sender'] == 'student']
    if not student_messages:
        return {
            'empathy_score': 10,
            'open_ended_score': 10,
            'active_listening_score': 10,
            'clarity_score': 10,
            'professionalism_score': 10,
            'overall_score': 50,
            'strengths': ['Attempted participation'],
            'areas_for_improvement': ['Add more empathy', 'Use open-ended questions'],
            'improved_response_examples': ['I can see that this is difficult for you. Can you tell me more about what worries you most?'],
            'feedback_summary': 'The conversation needs more therapeutic exploration and validation.'
        }

    empathy, open_ended, active, clarity, professionalism = [], [], [], [], []

    for text in student_messages:
        lower = text.lower()
        empathy.append(25 if any(k in lower for k in ['i understand', 'i can see', 'you seem', 'that sounds', 'you feel']) else 15)
        open_ended.append(20 if '?' in text and any(k in lower for k in ['what', 'how', 'can you tell me']) else 10)
        active.append(20 if any(k in lower for k in ['tell me more', 'can you share', 'what concerns']) else 12)
        clarity.append(25 if len(text.split()) >= 6 else 18)
        professionalism.append(30 if not any(k in lower for k in ['calm down', 'do not worry', "don't worry", 'you should']) else 15)

    empathy_score = round(mean(empathy))
    open_ended_score = round(mean(open_ended))
    active_score = round(mean(active))
    clarity_score = round(mean(clarity))
    professionalism_score = round(mean(professionalism))
    overall = empathy_score + open_ended_score + active_score + clarity_score + professionalism_score

    strengths = []
    improvements = []
    examples = []

    if empathy_score >= 20:
        strengths.append('Used validating or empathy-based language.')
    else:
        improvements.append('Increase empathy and validation in responses.')
    if open_ended_score >= 16:
        strengths.append('Asked open-ended questions to explore feelings.')
    else:
        improvements.append('Ask more open-ended questions instead of closed reassurance.')
    if professionalism_score >= 24:
        strengths.append('Maintained a professional and respectful tone.')
    else:
        improvements.append('Avoid false reassurance and directive statements.')

    examples.extend([
        'I can see that you are feeling overwhelmed right now. Can you tell me more about what worries you the most?',
        'It sounds like this situation is very difficult for you. What would help you feel more supported right now?'
    ])

    if not improvements:
        improvements.append('Continue strengthening reflective listening for deeper exploration.')

    return {
        'empathy_score': empathy_score,
        'open_ended_score': open_ended_score,
        'active_listening_score': active_score,
        'clarity_score': clarity_score,
        'professionalism_score': professionalism_score,
        'overall_score': overall,
        'strengths': strengths,
        'areas_for_improvement': improvements,
        'improved_response_examples': examples,
        'feedback_summary': 'The session was evaluated using empathy, questioning, active listening, clarity, and professionalism criteria.'
    }
