# Study Buddy Finder

A responsive full-stack student matching demo. The client is Next.js + TypeScript + Tailwind; the API is FastAPI with SQLAlchemy. It uses SQLite locally by default and accepts `DATABASE_URL` for PostgreSQL.

## Run

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn main:app --reload --port 8000

cd ../frontend
npm install
npm run dev
```

Open http://localhost:3000. Demo users are seeded automatically; register a new account to try onboarding.
