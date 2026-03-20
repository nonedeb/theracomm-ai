# TheraComm AI

TheraComm AI is a functional MVP web app for nursing education focused on therapeutic communication training.

## Included modules
- AI Patient Simulator (chat-based OSCE style)
- Scenario-Based Decision Trainer
- Faculty Analytics Dashboard
- Login and registration for student/faculty users

## Stack
- Frontend: React + Vite
- Backend: Flask + SQLAlchemy
- Database: Supabase Postgres or local SQLite for development
- AI: OpenAI API optional, with fallback local evaluator and mock patient replies
- Deploy: Render + Supabase

## Project structure
```
theracomm-ai/
├── backend/
└── frontend/
```

## Local development

### 1) Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

For local-only testing, you may change `DATABASE_URL` in `.env` to:
```env
DATABASE_URL=sqlite:///theracomm.db
```

Then run:
```bash
python run.py
```

### 2) Frontend
Open another terminal:
```bash
cd frontend
npm install
npm run dev
```

## Demo accounts
- Student: `student@theracomm.ai` / `student123`
- Faculty: `faculty@theracomm.ai` / `faculty123`

## OpenAI integration
Add your API key in `backend/.env` or Render env vars:
```env
OPENAI_API_KEY=your_key_here
```
If no key is provided, the app still works using built-in fallback logic.

## Deploy on Render + Supabase

This repo is now patterned for your **Render + Supabase** setup.

### A. Create your Supabase database
1. Open your Supabase project.
2. Go to **Project Settings → Database**.
3. Copy the **Connection string**.
4. Use the **Direct connection** string if available.
5. Make sure it includes `sslmode=require`.

Example:
```env
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres?sslmode=require
```

### B. Deploy to Render
1. Push this project to GitHub.
2. In Render, click **New + → Blueprint**.
3. Connect your repo. Render will detect `render.yaml`.
4. When creating the backend service, set these env vars in Render:
   - `DATABASE_URL` = your Supabase Postgres connection string
   - `OPENAI_API_KEY` = optional
5. Deploy both services.

### Important notes
- The frontend automatically uses your backend Render URL.
- The frontend app automatically appends `/api`, so do **not** add `/api` manually in `VITE_API_BASE_URL`.
- The backend normalizes `postgres://` and `postgresql://` URLs for SQLAlchemy and enforces SSL for Supabase when needed.
- On first run, the backend seeds demo users and built-in scenarios.

## Manual Render setup

### Backend web service
- Root Directory: `backend`
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn run:app`
- Environment Variables:
  - `DATABASE_URL` = Supabase connection string
  - `SECRET_KEY` = any random secret
  - `OPENAI_API_KEY` = optional
  - `CORS_ORIGINS` = your frontend Render URL

### Frontend static site
- Root Directory: `frontend`
- Build Command: `npm install && npm run build`
- Publish Directory: `dist`
- Environment Variable:
  - `VITE_API_BASE_URL` = your backend Render URL only

## Suggested next improvements
- Supabase Auth integration
- Better analytics charts
- Section-based faculty filtering
- Voice-to-text module
- Exportable reports
- Rubric customization by faculty
