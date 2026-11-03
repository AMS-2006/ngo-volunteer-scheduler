"""
seed_volunteers.py
──────────────────
Populates the database with fictional volunteer accounts and profiles
for hackathon demonstration purposes.

Usage (from the backend/ directory):
  python seed_volunteers.py

Requires DATABASE_URL to be set in .env or as an environment variable.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.database.connection import SessionLocal, Base, engine
from app.core.security import hash_password
from app.models.user import User
from app.models.volunteer import VolunteerProfile

import app.database.models  # noqa – ensure all models are registered

# ── Create tables if they don't exist yet ─────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ── Seed data ─────────────────────────────────────────────────────────────────
VOLUNTEERS = [
    {
        "user": {
            "full_name": "Rahul Sharma",
            "email": "rahul.sharma@example.com",
            "password": "Demo@1234",
            "role": "volunteer",
        },
        "profile": {
            "phone": "+91 98765 43210",
            "address": "24 MG Road",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560001",
            "age": 24,
            "gender": "male",
            "occupation_type": "working_professional",
            "organization_name": "Infosys Ltd.",
            "affiliation": None,
            "interests": ["Healthcare", "Environment", "Disaster Relief"],
            "volunteering_frequency_per_month": 4,
            "volunteering_hours_per_week": 8.0,
            "max_travel_distance_km": 30.0,
            "skills": ["First Aid", "Communication", "Team Leadership"],
            "availability": ["Weekend Mornings", "Weekend Afternoons"],
            "experience_months": 18,
            "bio": "Passionate about environmental causes and community health. Certified first-aider.",
        },
    },
    {
        "user": {
            "full_name": "Priya Nair",
            "email": "priya.nair@example.com",
            "password": "Demo@1234",
            "role": "volunteer",
        },
        "profile": {
            "phone": "+91 91234 56789",
            "address": "8 Koramangala 4th Block",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560034",
            "age": 22,
            "gender": "female",
            "occupation_type": "student",
            "organization_name": "Christ University",
            "affiliation": "NSS Unit 7",
            "interests": ["Education", "Women Empowerment", "Child Welfare"],
            "volunteering_frequency_per_month": 6,
            "volunteering_hours_per_week": 12.0,
            "max_travel_distance_km": 20.0,
            "skills": ["Teaching", "Counselling", "Event Management"],
            "availability": ["Weekday Evenings", "Weekend Mornings", "Weekend Afternoons"],
            "experience_months": 8,
            "bio": "NSS volunteer with a focus on rural education and women's empowerment programs.",
        },
    },
    {
        "user": {
            "full_name": "Aman Verma",
            "email": "aman.verma@example.com",
            "password": "Demo@1234",
            "role": "volunteer",
        },
        "profile": {
            "phone": "+91 93456 78901",
            "address": "55 Whitefield Main Road",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560066",
            "age": 28,
            "gender": "male",
            "occupation_type": "working_professional",
            "organization_name": "Wipro Technologies",
            "affiliation": None,
            "interests": ["Animal Welfare", "Environment", "Disaster Relief"],
            "volunteering_frequency_per_month": 2,
            "volunteering_hours_per_week": 4.0,
            "max_travel_distance_km": 15.0,
            "skills": ["Driving", "Logistics", "Photography"],
            "availability": ["Weekend Afternoons"],
            "experience_months": 6,
            "bio": "Animal lover and environment enthusiast. I help with logistics and documentation.",
        },
    },
    {
        "user": {
            "full_name": "Sneha Reddy",
            "email": "sneha.reddy@example.com",
            "password": "Demo@1234",
            "role": "volunteer",
        },
        "profile": {
            "phone": "+91 87654 32109",
            "address": "12 Jayanagar 9th Block",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560041",
            "age": 26,
            "gender": "female",
            "occupation_type": "working_professional",
            "organization_name": "Apollo Hospitals",
            "affiliation": None,
            "interests": ["Healthcare", "Senior Care", "Disability Support"],
            "volunteering_frequency_per_month": 5,
            "volunteering_hours_per_week": 10.0,
            "max_travel_distance_km": 25.0,
            "skills": ["First Aid", "Nursing Assistance", "Medical Camp Organisation"],
            "availability": ["Weekday Mornings", "Weekend Mornings", "Weekend Afternoons"],
            "experience_months": 30,
            "bio": "Healthcare professional volunteering at medical camps and senior care centers.",
        },
    },
    {
        "user": {
            "full_name": "Arjun Menon",
            "email": "arjun.menon@example.com",
            "password": "Demo@1234",
            "role": "volunteer",
        },
        "profile": {
            "phone": "+91 76543 21098",
            "address": "3 Indiranagar 100 Feet Road",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560038",
            "age": 21,
            "gender": "male",
            "occupation_type": "student",
            "organization_name": "RV College of Engineering",
            "affiliation": "NCC Air Wing",
            "interests": ["Environment", "Education", "Disaster Relief"],
            "volunteering_frequency_per_month": 8,
            "volunteering_hours_per_week": 16.0,
            "max_travel_distance_km": 40.0,
            "skills": ["Web Development", "Data Entry", "Social Media", "Teaching"],
            "availability": ["Weekday Afternoons", "Weekday Evenings", "Weekend Mornings", "Weekend Afternoons"],
            "experience_months": 12,
            "bio": "Tech-savvy NCC cadet with a knack for digital volunteering and field operations.",
        },
    },
    {
        "user": {
            "full_name": "Divya Krishnan",
            "email": "divya.krishnan@example.com",
            "password": "Demo@1234",
            "role": "volunteer",
        },
        "profile": {
            "phone": "+91 65432 10987",
            "address": "7 Basavanagudi",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560004",
            "age": 45,
            "gender": "female",
            "occupation_type": "homemaker",
            "organization_name": None,
            "affiliation": "Rotary Club Bengaluru South",
            "interests": ["Child Welfare", "Women Empowerment", "Senior Care"],
            "volunteering_frequency_per_month": 3,
            "volunteering_hours_per_week": 6.0,
            "max_travel_distance_km": 10.0,
            "skills": ["Cooking", "Counselling", "Fundraising", "Communication"],
            "availability": ["Weekday Mornings", "Weekday Afternoons"],
            "experience_months": 60,
            "bio": "Long-time Rotary volunteer focused on child nutrition and women's welfare programs.",
        },
    },
    {
        "user": {
            "full_name": "NGO Admin",
            "email": "admin@ngovolunteer.org",
            "password": "Admin@Secure1",
            "role": "admin",
        },
        "profile": None,  # Admins don't have volunteer profiles
    },
]


def seed():
    db = SessionLocal()
    created = 0
    skipped = 0

    try:
        for entry in VOLUNTEERS:
            udata = entry["user"]

            # Skip if user already exists
            existing = db.query(User).filter(User.email == udata["email"]).first()
            if existing:
                print(f"  SKIP  {udata['email']} (already exists)")
                skipped += 1
                continue

            user = User(
                full_name=udata["full_name"],
                email=udata["email"],
                password_hash=hash_password(udata["password"]),
                role=udata["role"],
            )
            db.add(user)
            db.flush()  # Get the generated user.id before committing

            pdata = entry.get("profile")
            if pdata:
                profile = VolunteerProfile(user_id=user.id, **pdata)
                db.add(profile)

            print(f"  CREATE {udata['role'].upper():10s}  {udata['full_name']} ({udata['email']})")
            created += 1

        db.commit()
        print(f"\n✅  Seeding complete: {created} created, {skipped} skipped.")

    except Exception as exc:
        db.rollback()
        print(f"\n❌  Seeding failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("🌱  Seeding volunteer database...\n")
    seed()
