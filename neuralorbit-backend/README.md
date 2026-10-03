# NeuralOrbit Backend

FastAPI AI backend for the NeuralOrbit AI Operating System.

> **Zero changes to the existing frontend.** This project lives completely separately from `neural-core-static/`.

---

## 📁 Structure

```
neuralorbit-backend/
├── app/
│   ├── main.py               ← FastAPI entry point
│   ├── config.py             ← Settings from .env
│   ├── database.py           ← Supabase client
│   ├── auth/                 ← JWT validation
│   ├── api/v1/               ← REST endpoints
│   │   ├── events.py
│   │   ├── decisions.py
│   │   ├── rewards.py
│   │   ├── recommendations.py
│   │   └── states.py
│   └── core/
│       ├── intelligence/     ← Reward engine + state engine
│       └── llm/              ← Mock LLM (Phase 1) → OpenAI (Phase 3)
├── scripts/
│   └── init_db.sql           ← Run this in Supabase SQL editor
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## 🚀 Quick Start

### Step 1 — Supabase Setup
1. Go to your Supabase Dashboard → **SQL Editor**
2. Run `scripts/init_db.sql` (creates all tables + seeds reward config)
3. Go to **Settings → API** and copy:
   - **Project URL**
   - **service_role key** (NOT the anon key)
   - **JWT Secret** (Settings → API → JWT Settings)

### Step 2 — Environment
```bash
cp .env.example .env
# Fill in SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET
```

### Step 3 — Run (Docker)
```bash
docker-compose up --build
```

### Step 3 — Run (without Docker)
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Step 4 — Test
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Server health check |
| `POST` | `/api/v1/events` | Log a business event (auto-scores reward) |
| `GET` | `/api/v1/events` | Fetch events for current user |
| `POST` | `/api/v1/decisions` | Manually log a decision |
| `GET` | `/api/v1/decisions` | Fetch decision log |
| `PATCH` | `/api/v1/decisions/{id}/outcome` | Mark decision applied/rejected |
| `GET` | `/api/v1/rewards/config` | View reward configuration |
| `GET` | `/api/v1/rewards/summary` | Reward totals + breakdown |
| `POST` | `/api/v1/rewards/manual` | Admin: manual reward score |
| `POST` | `/api/v1/recommend` | Get AI recommendation |
| `GET` | `/api/v1/states/all` | All module states |
| `GET` | `/api/v1/states/{module}` | Specific module state |

---

## 🔑 Demo (AUTH_REQUIRED=false in dev)

```bash
# Log an event
curl -X POST http://localhost:8000/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{"module":"crm","event_type":"meeting_booked","payload":{"lead":"ACME Corp"}}'

# Get an AI recommendation
curl -X POST http://localhost:8000/api/v1/recommend \
  -H "Content-Type: application/json" \
  -d '{"module":"crm","question":"Which leads should I prioritize today?"}'

# View reward summary
curl http://localhost:8000/api/v1/rewards/summary
```
