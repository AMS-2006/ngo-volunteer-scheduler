# NGO Volunteer Scheduler

> A centralized web-based volunteer scheduling and coordination platform for NGOs.
> Hackathon project — Problem Statement WEB-12.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend Framework | FastAPI (Python 3.11+) |
| Database | PostgreSQL |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| Authentication | JWT + OAuth2 (Argon2 password hashing) |
| Validation | Pydantic v2 |
| API Docs | Swagger UI (`/docs`) |

---

## Project Structure

```
volunteer_scheduling_system/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── auth.py          # Register, Login, /me
│   │   │   │   └── volunteers.py    # Volunteer profile CRUD
│   │   │   └── router.py            # Central API router
│   │   ├── core/
│   │   │   ├── config.py            # App settings (reads .env)
│   │   │   ├── database.py          # SQLAlchemy engine + session
│   │   │   ├── security.py          # JWT + Argon2 password hashing
│   │   │   └── deps.py              # FastAPI auth dependencies
│   │   ├── models/
│   │   │   ├── user.py              # User ORM model (auth + role)
│   │   │   └── volunteer.py         # VolunteerProfile ORM model
│   │   ├── schemas/
│   │   │   ├── auth.py              # Register/Login/Token schemas
│   │   │   └── volunteer.py         # Profile Create/Update/Out schemas
│   │   └── main.py                  # FastAPI app entry point
│   ├── alembic/
│   │   ├── env.py                   # Alembic migration environment
│   │   ├── script.py.mako           # Migration file template
│   │   └── versions/                # Migration scripts go here
│   ├── alembic.ini                  # Alembic configuration
│   ├── seed_volunteers.py           # Demo data seeder
│   └── requirements.txt
└── README.md
```

---

## Quick Start

### 1. Clone & enter the backend
```bash
git clone https://github.com/AMS-2006/ngo-volunteer-scheduler.git
cd ngo-volunteer-scheduler/backend
```

### 2. Create and activate a virtual environment
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
```bash
cp .env.example .env
# Edit .env and set your PostgreSQL DATABASE_URL and a strong SECRET_KEY
```

### 5. Create the PostgreSQL database
```sql
CREATE DATABASE ngo_volunteer_db;
```

### 6. Run Alembic migrations
```bash
alembic upgrade head
```

### 7. Seed demo data
```bash
python seed_volunteers.py
```

### 8. Start the development server
```bash
uvicorn app.main:app --reload --port 8000
```

Visit **http://localhost:8000/docs** for the interactive Swagger UI.

---

## API Endpoints — Module 2: Volunteer Management

### Authentication
| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Register a new account | Public |
| `POST` | `/api/v1/auth/login` | Log in, receive JWT | Public |
| `GET` | `/api/v1/auth/me` | Get current user | Bearer |

### Volunteer Profile
| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/api/v1/volunteers/profile` | Create my profile | Volunteer |
| `GET` | `/api/v1/volunteers/profile` | Get my profile | Volunteer |
| `PATCH` | `/api/v1/volunteers/profile` | Update my profile (partial) | Volunteer |
| `DELETE` | `/api/v1/volunteers/profile` | Delete my profile | Volunteer |
| `GET` | `/api/v1/volunteers/` | List all volunteers (filtered) | Admin |
| `GET` | `/api/v1/volunteers/{user_id}` | Get any volunteer's profile | Admin |
| `GET` | `/api/v1/volunteers/{user_id}/summary` | Lightweight summary card | Admin |

### Demo Credentials (after seeding)
| Role | Email | Password |
|---|---|---|
| Admin | `admin@ngovolunteer.org` | `Admin@Secure1` |
| Volunteer | `rahul.sharma@example.com` | `Demo@1234` |
| Volunteer | `sneha.reddy@example.com` | `Demo@1234` |

---

## Volunteer Profile Fields

| # | Category | Fields |
|---|---|---|
| 1 | Personal | name, phone, address, city, state, pincode, age, date_of_birth, gender |
| 2 | Occupation | occupation_type, organization_name, affiliation |
| 3 | Interests | interests (array) |
| 4 | Frequency | volunteering_frequency_per_month |
| 5 | Hours | volunteering_hours_per_week |
| 6 | Travel | max_travel_distance_km |
| 7 | Skills | skills (array) |
| + | Extras | availability, experience_months, bio, profile_picture_url |

---

## Modules Roadmap

| Module | Status | Owner |
|---|---|---|
| Module 1 – Admin & Event Management | 🔜 Next | Member 1 |
| **Module 2 – Volunteer Management** | ✅ Complete | Member 1 |
| Module 3 – Scheduling Engine | 🔜 Next | Member 2 |
| Module 4 – Smart Matching | 🔜 Next | Member 2 |
| Module 5 – Coverage Dashboard | 🔜 Next | Member 3 |
| Module 6 – Reminders | 🔜 Next | Member 3 |
| Module 7 – Attendance | 🔜 Extension | Member 3 |
