# Volunteer Connect — SPEC

Two-sided NGO ↔ volunteer scheduling platform. FastAPI + MongoDB backend (built-in stack chosen by user instead of Supabase), React 19 + Vite + Tailwind v4 + TS frontend, i18next (en/kn/hi/ta/te), Leaflet + OSM maps, Recharts.

## Auth & roles
- Email/password, pbkdf2 hashes, httpOnly cookie `vc_session` (sessions collection, 14d TTL). `GET /api/auth/me`.
- Role (`ngo` | `volunteer`) stored on `users`, chosen at registration, never editable. Guards `require_ngo` / `require_volunteer` re-read role from DB → 403. Objects reached by id are ownership-checked → 404.
- Password reset: `/api/auth/forgot-password` sends a real email via Emergent-managed Resend to non-demo accounts (1h single-use token, link `${APP_URL}/reset-password?token=`). Seeded demo inboxes are fictional → no email; response says so.

## Collections
users, sessions, password_resets, ngo_profiles, volunteer_profiles (skills, interests, preferred_activities, availability{days,slots}, lat/lng, preferred_travel_radius, privacy{share_location, share_contact, replacement_opt_in}), events (status draft|published|unpublished, emergency, translations{lang:{title,description}}), shifts (capacity, filled counter, required_skills[{skill,count}]), registrations (active flag, partial unique index (volunteer_id, shift_id) where active; status confirmed|cancelled|completed|absent; source direct|replacement|emergency; replaced_by), replacement_invitations (pending|accepted|declined|expired|filled, urgent), notifications (type + params → translated client-side; dedupe_key for reminders), attendance.

## Key logic (backend/lib/logic.py)
- Times are IST local. Availability slots: morning 6–12, afternoon 12–17, evening 17–22.
- Registration: published + before deadline + shift not started + not duplicate + inside availability + no overlapping active shift + atomic `filled < capacity` claim.
- Coverage: headcount + greedy skill matching → fully_staffed | fully_booked (full but skill gap) | partially_staffed (≥50%) | critical_shortage.
- Cancellation: status→cancelled, filled−1, `last_minute` if <48h, engine run, NGO notified with candidate count.
- Matching: mandatory filters (opt-in, availability>0, no overlap, not on shift, relevant skill, within radius if location shared) then score = 40·skills + 30·availability + 20·distance (0.5 neutral if unknown, shown as "Distance unavailable") + 10·interests − fairness (≤5 pts for recent 30-day hours + upcoming commitments; cancellations never penalised).
- Accept invitation: atomic claim of the cancelled registration (`replaced_by: None`) + atomic seat claim; other pending invites for that vacancy → filled.
- Emergency mode: `/api/ngo/emergency` marks event emergency and sends urgent invites to top 2×needed candidates.
- Reminders 24h / 2h generated in-app on read of notifications/dashboard (no push/email/SMS).

## Seed (`cd /app/backend && python seed.py`, idempotent, dates relative to today)
3 NGOs, 14 volunteers, 10 events (1 draft, 2 past with attendance). Cancellation scenario: Rohan Gowda cancelled "Community Food Distribution Drive" (tomorrow) 11:00–14:00 shift (needs logistics). Ranked candidates: Kavya Reddy ≈98.8, Arjun Nair ≈92.7, Divya Hegde ≈88.8 (distance unavailable). Overlap test: Priya is on Food Drive 08:00–11:00 tomorrow; "Senior Citizens Health Check-up" 09:00–12:00 tomorrow conflicts. All demo records have is_demo=true and show a "Demo data" badge.

## Frontend routes
Public: / , /about, /register, /register/:role, /login, /forgot-password, /reset-password.
NGO (/ngo/*): dashboard, profile, events, events/new, events/:id (shift mgmt + registrations + attendance), events/:id/edit, registrations, coverage, cancellations (Smart Cancellation Manager + emergency), volunteers, analytics, notifications.
Volunteer (/volunteer/*): dashboard, profile, discover, events/:id, ngos/:id, registrations, invitations, history, notifications.
