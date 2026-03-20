# TheraComm AI Clean Build

A clean Flask + Supabase/Render-ready web app for therapeutic communication training.

## Demo accounts
- Manager: `manager@theracomm.ai` / `Manager123!`
- Faculty: `faculty@theracomm.ai` / `Faculty123!`
- Student: `student@theracomm.ai` / `Student123!`

## Features
- Role-based login
- Student dashboard
- Faculty dashboard
- Manager dashboard
- AI patient simulator
- Result tracking
- Supabase/Postgres-ready configuration

## Local setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Render setup
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Set `DATABASE_URL` to your Supabase Postgres connection string
- Set `SECRET_KEY`
- Set `OPENAI_API_KEY` if you want live AI scoring

## Supabase note
This app uses psycopg v3 and disables prepared statements for compatibility with Supabase poolers.
