# TheraComm AI v1.2

Render + Supabase ready Flask web app for therapeutic communication practice, assessment, faculty review, and manager administration.

## Setup
1. Upload project to GitHub.
2. Deploy on Render.
3. Set environment variables:
   - `SECRET_KEY`
   - `DATABASE_URL` (Supabase Postgres)
   - `OPENAI_API_KEY` (optional)
4. Visit `/init-db` once.
5. Log in.

## Demo Accounts
- manager@theracomm.ai / Manager123!
- faculty@theracomm.ai / Faculty123!
- student@theracomm.ai / Student123!

## Main Modules
- Student: chat practice, decision practice, 20-scenario assessment, results
- Faculty: dashboard, records, comments, recommendations
- Manager: user CRUD, scenario CRUD, optional library bank
