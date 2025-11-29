"""Create database tables and seed sample data for Traffic_Backend.

Run:
  C:/Users/abhis/HSC_NavDrishti_AHM/.venv/Scripts/python.exe init_db.py
"""
from sqlalchemy.exc import SQLAlchemyError
import os
import sys
# Ensure repo root / Traffic_Backend is on path for imports when run as script
this_dir = os.path.dirname(os.path.abspath(__file__))
if this_dir not in sys.path:
    sys.path.insert(0, this_dir)

from Traffic_Backend.db_config import engine, SessionLocal
from Traffic_Backend.models import Base, Project, User
from Traffic_Backend.auth import create_user


def create_tables():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created")


def seed_sample_projects():
    print("Seeding sample projects...")
    db = SessionLocal()
    try:
        # Check if there are already projects
        existing = db.query(Project).count()
        if existing > 0:
            print(f"{existing} project(s) already exist — skipping seed.")
            return

        samples = [
            Project(name="Ahmedabad Road Repair", status="active", start_lat=23.0225, start_lon=72.5714),
            Project(name="Surat Diversion Study", status="planned", start_lat=21.1702, start_lon=72.8311),
            Project(name="Vadodara Emission Reduction", status="completed", start_lat=22.3072, start_lon=73.1812)
        ]
        db.add_all(samples)
        db.commit()
        print(f"Seeded {len(samples)} projects")
    except SQLAlchemyError as e:
        db.rollback()
        print(f"Error seeding projects: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    create_tables()
    seed_sample_projects()
    # seed admin user if not present
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == 'admin').first()
        if admin:
            print('Admin user already exists')
        else:
            create_user(db, 'admin', 'adminpass', email='admin@example.com', roles='admin')
            print('Created admin user with username "admin" and password "adminpass"')
    finally:
        db.close()
