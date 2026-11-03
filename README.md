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

### 9. Run the Test Suite
```bash
pytest backend/app/tests/ -v
```

Visit **http://localhost:8000/docs** for the interactive Swagger UI.

---

## API Endpoints

### Authentication
| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Register a new account | Public |
| `POST` | `/api/v1/auth/login` | Log in, receive JWT | Public |
| `GET` | `/api/v1/auth/me` | Get current user | Bearer |

### NGO & Event Management (Module 1)
| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/api/v1/ngo/` | Create NGO profile | Admin |
| `GET` | `/api/v1/ngo/` | Get my NGO profile | Admin |
| `PATCH` | `/api/v1/ngo/` | Update NGO profile | Admin |
| `POST` | `/api/v1/events/` | Create new event (starts as draft) | Admin |
| `GET` | `/api/v1/events/` | List published events | Public |
| `GET` | `/api/v1/events/admin` | List all events for admin's NGO | Admin |
| `GET` | `/api/v1/events/{id}` | Get event details with shifts | Public |
| `PATCH` | `/api/v1/events/{id}` | Update event | Admin |
| `DELETE` | `/api/v1/events/{id}` | Delete event and its shifts | Admin |
| `POST` | `/api/v1/events/{id}/publish` | Publish event | Admin |
| `POST` | `/api/v1/events/{id}/shifts/` | Add shift to event | Admin |
| `GET` | `/api/v1/events/{id}/shifts/` | List all shifts for an event | Public |
| `PATCH` | `/api/v1/events/{id}/shifts/{shift_id}` | Update shift | Admin |
| `DELETE` | `/api/v1/events/{id}/shifts/{shift_id}` | Delete shift | Admin |

### Volunteer Management (Module 2)
| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/api/v1/volunteers/profile` | Create my profile | Volunteer |
| `GET` | `/api/v1/volunteers/profile` | Get my profile | Volunteer |
| `PATCH` | `/api/v1/volunteers/profile` | Update my profile (partial) | Volunteer |
| `DELETE` | `/api/v1/volunteers/profile` | Delete my profile | Volunteer |
| `GET` | `/api/v1/volunteers/` | List all volunteers (filtered) | Admin |
| `GET` | `/api/v1/volunteers/{user_id}` | Get any volunteer's profile | Admin |
| `GET` | `/api/v1/volunteers/{user_id}/summary` | Lightweight summary card | Admin |

### Smart Shift Scheduling Engine (Module 3)
| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `GET` | `/api/v1/registrations/shifts/available` | Browse shifts with live capacity, remaining slots & personal conflict checks | Volunteer / Admin |
| `POST` | `/api/v1/registrations/` | Register for a shift (or join FIFO waitlist if full) | Volunteer |
| `DELETE` | `/api/v1/registrations/{id}` | Cancel registration (triggers automatic FIFO waitlist promotion) | Volunteer / Admin |
| `GET` | `/api/v1/registrations/my` | View my registered shifts (confirmed & waitlisted) | Volunteer |
| `GET` | `/api/v1/registrations/shift/{id}` | View all registrations for a shift | Admin |
| `GET` | `/api/v1/registrations/availability` | View declared weekly/date availability windows | Volunteer |
| `POST` | `/api/v1/registrations/availability` | Add an availability window (day of week, time range) | Volunteer |
| `DELETE` | `/api/v1/registrations/availability/{id}` | Delete an availability window | Volunteer |

### Demo Credentials (after seeding)
| Role | Email | Password |
|---|---|---|
| Admin | `admin@ngovolunteer.org` | `Admin@Secure1` |
| Volunteer | `rahul.sharma@example.com` | `Demo@1234` |
| Volunteer | `sneha.reddy@example.com` | `Demo@1234` |

---

## Modules Roadmap

| Module | Status | Owner |
|---|---|---|
| **Module 1 – Admin & Event Management** | ✅ Complete | Member 1 |
| **Module 2 – Volunteer Management** | ✅ Complete | Member 1 |
| **Module 3 – Scheduling Engine** | ✅ Complete | Member 2 |
| Module 4 – Smart Matching | 🔜 Next | Member 2 |
| Module 5 – Coverage Dashboard | 🔜 Next | Member 3 |
| Module 6 – Reminders | 🔜 Next | Member 3 |
| Module 7 – Attendance | 🔜 Extension | Member 3 |
