# TheraComm AI

Clean Flask + Supabase + Render build.

## Deploy steps
1. Push this folder to GitHub.
2. Create a new Render web service from the repo.
3. Set `DATABASE_URL` to your Supabase Postgres connection string.
4. Deploy.
5. Visit `/init-db` once to create tables and seed demo data.
   - If you set `INIT_DB_TOKEN`, call `/init-db?token=YOUR_TOKEN`.

## Demo accounts
- manager@theracomm.ai / Manager123!
- faculty@theracomm.ai / Faculty123!
- student@theracomm.ai / Student123!

## Notes
- `/health` is used for Render health checks.
- The app does not auto-seed on startup to keep cold starts lighter.
