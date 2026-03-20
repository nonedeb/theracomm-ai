# TheraComm AI (Flask Pattern Version)

A Render-ready Flask web app patterned after the uploaded NCP & FDAR AI Analyzer structure.

## Features
- Role-based login: manager, faculty, student
- AI Patient Simulator (chat-based OSCE)
- Scenario-Based Decision Trainer
- Student feedback and scoring
- Faculty dashboard and curriculum insights
- Manager user overview
- Supabase / PostgreSQL-ready via `DATABASE_URL`
- Render-ready via `render.yaml`

## Demo accounts
- manager@theracomm.ai / Manager123!
- faculty@theracomm.ai / Faculty123!
- student@theracomm.ai / Student123!

## Environment variables
- `SECRET_KEY`
- `DATABASE_URL`
- `OPENAI_API_KEY` (optional)
- `OPENAI_MODEL` (optional)

## Local run
```bash
pip install -r requirements.txt
python app.py
```

## Render
Use Blueprint or a Python Web Service.
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`
