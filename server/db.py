"""
CivicPilot Database Layer
Dual-mode SQLAlchemy support:
- Supabase PostgreSQL (production / hackathon live backend)
- SQLite (offline fallback / testing)
"""

import os
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Boolean, 
    DateTime, ForeignKey, Text, JSON
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
import uuid

load_dotenv()

DATABASE_MODE = os.getenv("DATABASE_MODE", "supabase").lower()
DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_MODE == "supabase" and DATABASE_URL:
    # Ensure psycopg2 dialect driver is specified for SQLAlchemy
    db_uri = DATABASE_URL
    if db_uri.startswith("postgresql://"):
        db_uri = db_uri.replace("postgresql://", "postgresql+psycopg2://", 1)
    
    engine = create_engine(
        db_uri,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=False
    )
else:
    # SQLite fallback
    os.makedirs(".data", exist_ok=True)
    sqlite_url = "sqlite:///.data/civic_pilot.db"
    engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """FastAPI dependency for DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------- Models -----------------

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False, default="citizen")  # 'citizen' or 'admin'
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    reports = relationship("Report", back_populates="user")


class Report(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    category = Column(String(100), nullable=False)  # 'roads_potholes', 'garbage', 'water', etc.
    description = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default="SUBMITTED", index=True)  # SUBMITTED, TRIAGED, ACKNOWLEDGED, ASSIGNED, IN_PROGRESS, RESOLVED, REJECTED
    severity = Column(String(10), nullable=False, default="P3")  # P1, P2, P3, P4
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    ward_id = Column(String(100), nullable=False, index=True)
    ward_name = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False)
    evidence_urls = Column(JSON, default=list)  # list of URLs
    poi_distance_m = Column(Float, nullable=True)
    poi_multiplier = Column(Float, default=1.0)
    sla_deadline = Column(DateTime(timezone=True), nullable=True)
    assigned_to = Column(String(255), nullable=True)
    resolution_proof_url = Column(Text, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    duplicate_of = Column(String(36), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
    upvotes = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="reports")
    events = relationship("ReportEvent", back_populates="report", cascade="all, delete-orphan")
    receipts = relationship("ReceiptModel", back_populates="report")


class ReportEvent(Base):
    __tablename__ = "report_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(String(36), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)  # CREATED, TRIAGED, ACKNOWLEDGED, ASSIGNED, RESOLVED, UPVOTED, DISPUTED
    payload = Column(JSON, default=dict)
    actor_role = Column(String(50), default="system")  # citizen, admin, system
    actor_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    report = relationship("Report", back_populates="events")


class ReceiptModel(Base):
    __tablename__ = "receipts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(100), unique=True, nullable=False, index=True)
    report_id = Column(String(36), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True, index=True)
    confirmation_number = Column(String(100), nullable=False)
    portal_name = Column(String(100), nullable=False)
    submitted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    receipt_url = Column(Text, nullable=True)
    signature = Column(Text, nullable=False)
    public_key = Column(Text, nullable=False)
    prev_hash = Column(String(64), nullable=False)
    ticket_hash = Column(String(64), nullable=False)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    report = relationship("Report", back_populates="receipts")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(String(100), primary_key=True)
    service = Column(String(100), nullable=False)
    status = Column(String(50), default="running")  # running, success, failed, waiting_human
    task_input = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    steps = relationship("AgentRunStep", back_populates="run", cascade="all, delete-orphan")


class AgentRunStep(Base):
    __tablename__ = "agent_run_steps"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(100), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    action = Column(String(100), nullable=False)
    target = Column(Text, nullable=True)
    status = Column(String(50), nullable=False)
    screenshot_url = Column(Text, nullable=True)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    run = relationship("AgentRun", back_populates="steps")


class Scheme(Base):
    __tablename__ = "schemes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scheme_code = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    ministry = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    eligibility_criteria = Column(JSON, default=dict)
    benefits = Column(Text, nullable=False)
    application_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PortalRegistry(Base):
    __tablename__ = "portal_registry"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portal_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    base_url = Column(Text, nullable=False)
    route_manifest = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def init_db():
    """Create tables if they do not exist (useful for SQLite or initial setup)."""
    Base.metadata.create_all(bind=engine)
