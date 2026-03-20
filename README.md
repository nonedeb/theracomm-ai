# TheraComm AI v1.1

Render + Supabase friendly Flask web app for therapeutic communication training.

## Features
- Role-based login: student, faculty, manager
- Chat-style AI patient simulator
- Scenario-based decision trainer
- Results tracking
- Faculty analytics dashboard
- User and scenario management
- Manual database initialization via `/init-db`

## Demo accounts
Run `/init-db` once after deployment, then use:
- manager@theracomm.ai / Manager123!
- faculty@theracomm.ai / Faculty123!
- student@theracomm.ai / Student123!

## Deploy
1. Push project to GitHub.
2. Deploy to Render.
3. Set `DATABASE_URL` and `SECRET_KEY`.
4. Visit `/init-db` once.
5. Log in.

## Notes
- For Supabase, use a direct or session pooler URL when possible.
- Prepared statements are disabled for psycopg compatibility.
