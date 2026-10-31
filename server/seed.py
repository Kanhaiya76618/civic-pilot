"""
CivicPilot Seed Script (Idempotent Upsert)
Populates Supabase PostgreSQL / SQLite with:
- 2 Demo Users (Citizen, Municipal Admin)
- 18 Realistic Civic Reports across 4 Wards (Bangalore BBMP, Pune PMC, Delhi)
- 1 SLA-Breached P1 Emergency Report
- 1 Deduplicated Pair (with spatial proximity link & upvotes)
- 1 Resolved Report with Verified Resolution Proof Photo
- 1 Agent-Filed Report with Tamper-Evident Ed25519 Cryptographic Receipt
- Real Welfare & Grievance Schemes
"""

import os
import json
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from server.db import (
    SessionLocal, User, Report, ReportEvent, ReceiptModel, 
    Scheme, PortalRegistry, init_db
)
from server.receipts import sign_receipt, compute_ticket_hash

def seed_database():
    init_db()
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        print("Starting idempotent seed of CivicPilot database...")

        # 1. SEED USERS
        users_data = [
            {"id": "00000000-0000-0000-0000-000000000001", "email": "citizen@demo.in", "name": "Aarav Sharma", "role": "citizen"},
            {"id": "00000000-0000-0000-0000-000000000002", "email": "admin@demo.in", "name": "Priya Nair (Municipal Desk Admin)", "role": "admin"}
        ]
        user_map = {}
        for u in users_data:
            existing = db.query(User).filter(User.email == u["email"]).first()
            if not existing:
                new_user = User(id=u["id"], email=u["email"], name=u["name"], role=u["role"], created_at=now)
                db.add(new_user)
                db.flush()
                user_map[u["role"]] = new_user.id
                print(f"Created user: {u['email']} ({u['role']})")
            else:
                user_map[u["role"]] = existing.id
                print(f"User already exists: {u['email']}")

        citizen_id = user_map.get("citizen", "00000000-0000-0000-0000-000000000001")
        admin_id = user_map.get("admin", "00000000-0000-0000-0000-000000000002")

        # 2. SEED SCHEMES
        schemes_data = [
            {
                "scheme_code": "PM-JAY",
                "name": "Ayushman Bharat PM Jan Arogya Yojana",
                "ministry": "Ministry of Health and Family Welfare",
                "description": "Health coverage of up to Rs 5 lakh per family per year for secondary and tertiary care hospitalization to over 12 crore poor and vulnerable families.",
                "eligibility_criteria": {"income_limit": 250000, "rural_deprivation_category": True, "ration_card": True},
                "benefits": "Cashless access to health care services for the beneficiary at the point of service (hospital).",
                "application_url": "https://beneficiary.nha.gov.in"
            },
            {
                "scheme_code": "PMAY-U",
                "name": "Pradhan Mantri Awas Yojana - Urban",
                "ministry": "Ministry of Housing and Urban Affairs",
                "description": "Provides central assistance to urban local bodies and other implementing agencies for housing eligible families in urban areas.",
                "eligibility_criteria": {"urban_resident": True, "no_pucca_house": True, "income_category": ["EWS", "LIG"]},
                "benefits": "Interest subsidy up to Rs 2.67 lakh or direct subsidy for house construction.",
                "application_url": "https://pmay-urban.gov.in"
            },
            {
                "scheme_code": "PM-SVANIDHI",
                "name": "PM Street Vendor's AtmaNirbhar Nidhi",
                "ministry": "Ministry of Housing and Urban Affairs",
                "description": "Special micro-credit facility for street vendors providing affordable working capital loans with interest subsidy.",
                "eligibility_criteria": {"street_vendor": True, "urban_local_body_id": True},
                "benefits": "Collateral-free working capital loan starting at Rs 10,000 with 7% interest subsidy on digital repayments.",
                "application_url": "https://pmsvanidhi.mohua.gov.in"
            }
        ]
        for s in schemes_data:
            existing_s = db.query(Scheme).filter(Scheme.scheme_code == s["scheme_code"]).first()
            if not existing_s:
                db.add(Scheme(
                    id=str(uuid.uuid4()),
                    scheme_code=s["scheme_code"],
                    name=s["name"],
                    ministry=s["ministry"],
                    description=s["description"],
                    eligibility_criteria=s["eligibility_criteria"],
                    benefits=s["benefits"],
                    application_url=s["application_url"],
                    created_at=now
                ))
                print(f"Created scheme: {s['scheme_code']}")

        # 3. SEED PORTAL REGISTRY
        portals_data = [
            {
                "portal_id": "cpgrams",
                "name": "CPGRAMS Central Public Grievance Portal",
                "base_url": "https://pgportal.gov.in",
                "route_manifest": {"form_path": "/Home/LodgeGrievance", "requires_otp": True, "sla_days": 21}
            },
            {
                "portal_id": "bbmp_sahaaya",
                "name": "BBMP Sahaaya 2.0 (Bengaluru)",
                "base_url": "https://bbmp2.karnataka.gov.in/sahaaya",
                "route_manifest": {"form_path": "/grievance/new", "requires_otp": False, "sla_days": 7}
            },
            {
                "portal_id": "pmc_care",
                "name": "PMC Care Portal (Pune)",
                "base_url": "https://punecorporation.org/pmc-care",
                "route_manifest": {"form_path": "/complaint", "requires_otp": True, "sla_days": 5}
            }
        ]
        for p in portals_data:
            existing_p = db.query(PortalRegistry).filter(PortalRegistry.portal_id == p["portal_id"]).first()
            if not existing_p:
                db.add(PortalRegistry(
                    id=str(uuid.uuid4()),
                    portal_id=p["portal_id"],
                    name=p["name"],
                    base_url=p["base_url"],
                    route_manifest=p["route_manifest"],
                    is_active=True,
                    updated_at=now
                ))
                print(f"Created portal: {p['portal_id']}")

        # 4. SEED REPORTS (18 realistic records across 4 wards)
        # Fixed UUIDs for the 3 special cases so they can be referenced idempotently
        p1_breach_id = "11111111-1111-1111-1111-111111111101"
        dup_parent_id = "22222222-2222-2222-2222-222222222201"
        dup_child_id = "22222222-2222-2222-2222-222222222202"
        resolved_rep_id = "33333333-3333-3333-3333-333333333301"
        agent_rep_id = "44444444-4444-4444-4444-444444444401"

        reports_seed = [
            # --- WARD 111 (Bangalore - Shantinagar) ---
            {
                "id": p1_breach_id,
                "category": "water",
                "description": "CRITICAL: Broken high-pressure water main causing structural flooding and road erosion right outside St. Joseph's Hospital emergency ramp.",
                "status": "ASSIGNED",
                "severity": "P1",
                "latitude": 12.9602,
                "longitude": 77.5998,
                "ward_id": "BBMP-111",
                "ward_name": "Shantinagar",
                "city": "Bengaluru",
                "evidence_urls": ["https://images.unsplash.com/photo-1541888946425-d0fbb18f15f7?w=800"],
                "poi_distance_m": 35.0,
                "poi_multiplier": 1.6,
                "sla_deadline": now - timedelta(hours=14),  # BREACHED SLA!
                "assigned_to": "BWSSB Emergency Rapid Response Team 3",
                "upvotes": 12,
                "created_at": now - timedelta(hours=38)
            },
            {
                "id": "11111111-1111-1111-1111-111111111102",
                "category": "roads_potholes",
                "description": "Continuous series of asphalt edge cracks and open trench left after optic fiber laying on Richmond Road.",
                "status": "TRIAGED",
                "severity": "P2",
                "latitude": 12.9654,
                "longitude": 77.6041,
                "ward_id": "BBMP-111",
                "ward_name": "Shantinagar",
                "city": "Bengaluru",
                "evidence_urls": ["https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?w=800"],
                "poi_distance_m": 120.0,
                "poi_multiplier": 1.2,
                "sla_deadline": now + timedelta(hours=28),
                "upvotes": 3,
                "created_at": now - timedelta(hours=6)
            },
            {
                "id": "11111111-1111-1111-1111-111111111103",
                "category": "garbage",
                "description": "Commercial waste dumping and uncollected wet garbage accumulating near Shantinagar Bus Station entrance.",
                "status": "SUBMITTED",
                "severity": "P3",
                "latitude": 12.9568,
                "longitude": 77.5942,
                "ward_id": "BBMP-111",
                "ward_name": "Shantinagar",
                "city": "Bengaluru",
                "evidence_urls": [],
                "poi_distance_m": 85.0,
                "poi_multiplier": 1.1,
                "sla_deadline": now + timedelta(hours=42),
                "upvotes": 2,
                "created_at": now - timedelta(hours=2)
            },
            {
                "id": "11111111-1111-1111-1111-111111111104",
                "category": "streetlights",
                "description": "Dark stretch of 4 consecutive non-functional sodium lamps along Langford Road walkway.",
                "status": "ACKNOWLEDGED",
                "severity": "P3",
                "latitude": 12.9610,
                "longitude": 77.6015,
                "ward_id": "BBMP-111",
                "ward_name": "Shantinagar",
                "city": "Bengaluru",
                "evidence_urls": [],
                "poi_distance_m": 160.0,
                "poi_multiplier": 1.0,
                "sla_deadline": now + timedelta(hours=50),
                "upvotes": 1,
                "created_at": now - timedelta(hours=10)
            },

            # --- WARD 151 (Bangalore - Koramangala) ---
            {
                "id": resolved_rep_id,
                "category": "roads_potholes",
                "description": "Deep 45cm asphalt pothole on 80 Feet Road junction near Sony World crossing.",
                "status": "RESOLVED",
                "severity": "P2",
                "latitude": 12.9345,
                "longitude": 77.6256,
                "ward_id": "BBMP-151",
                "ward_name": "Koramangala",
                "city": "Bengaluru",
                "evidence_urls": ["https://images.unsplash.com/photo-1578916171728-46686eac8d58?w=800"],
                "poi_distance_m": 90.0,
                "poi_multiplier": 1.2,
                "sla_deadline": now - timedelta(hours=2),
                "assigned_to": "Ward 151 Asphalt Paving Division",
                "resolution_proof_url": "https://images.unsplash.com/photo-1578916171728-46686eac8d58?w=800",
                "resolution_notes": "Permanent hot-mix bitumen filling applied and compacted. Road leveled.",
                "upvotes": 7,
                "created_at": now - timedelta(days=2)
            },
            {
                "id": agent_rep_id,
                "category": "drainage",
                "description": "Stormwater drain blocked by construction debris causing backflow during evening rains.",
                "status": "IN_PROGRESS",
                "severity": "P2",
                "latitude": 12.9352,
                "longitude": 77.6138,
                "ward_id": "BBMP-151",
                "ward_name": "Koramangala",
                "city": "Bengaluru",
                "evidence_urls": ["https://images.unsplash.com/photo-1541888946425-d0fbb18f15f7?w=800"],
                "poi_distance_m": 110.0,
                "poi_multiplier": 1.2,
                "sla_deadline": now + timedelta(hours=18),
                "assigned_to": "BBMP Stormwater Drain Subdivision South",
                "upvotes": 5,
                "created_at": now - timedelta(hours=20)
            },
            {
                "id": "11111111-1111-1111-1111-111111111105",
                "category": "garbage",
                "description": "Overflowing public dumper bin behind 5th Block BBMP playground attracting stray animals.",
                "status": "TRIAGED",
                "severity": "P3",
                "latitude": 12.9328,
                "longitude": 77.6190,
                "ward_id": "BBMP-151",
                "ward_name": "Koramangala",
                "city": "Bengaluru",
                "evidence_urls": [],
                "poi_distance_m": 40.0,
                "poi_multiplier": 1.3,
                "sla_deadline": now + timedelta(hours=30),
                "upvotes": 3,
                "created_at": now - timedelta(hours=8)
            },
            {
                "id": "11111111-1111-1111-1111-111111111106",
                "category": "water",
                "description": "Low water pressure and brown turbidity in municipal supply line on 1st Main 7th Block.",
                "status": "SUBMITTED",
                "severity": "P3",
                "latitude": 12.9301,
                "longitude": 77.6212,
                "ward_id": "BBMP-151",
                "ward_name": "Koramangala",
                "city": "Bengaluru",
                "evidence_urls": [],
                "poi_distance_m": 250.0,
                "poi_multiplier": 1.0,
                "sla_deadline": now + timedelta(hours=60),
                "upvotes": 1,
                "created_at": now - timedelta(hours=3)
            },

            # --- WARD 12 (Pune PMC - Kothrud) ---
            # Duplicate pair demonstration:
            {
                "id": dup_parent_id,
                "category": "roads_potholes",
                "description": "Dangerous 2-meter wide asphalt crater on Paud Road outside Kothrud Depot bus exit.",
                "status": "TRIAGED",
                "severity": "P2",
                "latitude": 18.5074,
                "longitude": 73.8077,
                "ward_id": "PMC-12",
                "ward_name": "Kothrud",
                "city": "Pune",
                "evidence_urls": ["https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?w=800"],
                "poi_distance_m": 25.0,
                "poi_multiplier": 1.4,
                "sla_deadline": now + timedelta(hours=14),
                "upvotes": 6,  # 1 original + 4 merged from duplicate + 1 upvote
                "created_at": now - timedelta(hours=12)
            },
            {
                "id": dup_child_id,
                "category": "roads_potholes",
                "description": "Huge pothole causing two-wheelers to skid on Paud Road near bus depot exit.",
                "status": "TRIAGED",
                "severity": "P2",
                "latitude": 18.5076,  # ~22 meters away from parent
                "longitude": 73.8078,
                "ward_id": "PMC-12",
                "ward_name": "Kothrud",
                "city": "Pune",
                "evidence_urls": ["https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?w=800"],
                "poi_distance_m": 28.0,
                "poi_multiplier": 1.4,
                "sla_deadline": now + timedelta(hours=14),
                "duplicate_of": dup_parent_id,  # Marked as duplicate!
                "upvotes": 4,
                "created_at": now - timedelta(hours=9)
            },
            {
                "id": "22222222-2222-2222-2222-222222222203",
                "category": "garbage",
                "description": "Construction rubble dumped on pedestrian footpath opposite MIT World Peace University gate.",
                "status": "ACKNOWLEDGED",
                "severity": "P2",
                "latitude": 18.5186,
                "longitude": 73.8152,
                "ward_id": "PMC-12",
                "ward_name": "Kothrud",
                "city": "Pune",
                "evidence_urls": [],
                "poi_distance_m": 40.0,
                "poi_multiplier": 1.5,
                "sla_deadline": now + timedelta(hours=22),
                "upvotes": 4,
                "created_at": now - timedelta(hours=7)
            },
            {
                "id": "22222222-2222-2222-2222-222222222204",
                "category": "streetlights",
                "description": "Flashing faulty LED streetlight creating glare at Nal Stop flyover entry.",
                "status": "ASSIGNED",
                "severity": "P3",
                "latitude": 18.5065,
                "longitude": 73.8290,
                "ward_id": "PMC-12",
                "ward_name": "Kothrud",
                "city": "Pune",
                "evidence_urls": [],
                "poi_distance_m": 120.0,
                "poi_multiplier": 1.1,
                "sla_deadline": now + timedelta(hours=36),
                "assigned_to": "PMC Electrical Maintenance Ward 12",
                "upvotes": 2,
                "created_at": now - timedelta(hours=16)
            },
            {
                "id": "22222222-2222-2222-2222-222222222205",
                "category": "drainage",
                "description": "Open manhole with missing cast iron lid on Karve Road service lane.",
                "status": "ASSIGNED",
                "severity": "P1",
                "latitude": 18.5052,
                "longitude": 73.8251,
                "ward_id": "PMC-12",
                "ward_name": "Kothrud",
                "city": "Pune",
                "evidence_urls": ["https://images.unsplash.com/photo-1541888946425-d0fbb18f15f7?w=800"],
                "poi_distance_m": 50.0,
                "poi_multiplier": 1.4,
                "sla_deadline": now + timedelta(hours=6),
                "assigned_to": "PMC Drainage Wing Quick Action Team",
                "upvotes": 9,
                "created_at": now - timedelta(hours=18)
            },

            # --- WARD 54 (Delhi - Karol Bagh) ---
            {
                "id": "33333333-3333-3333-3333-333333333302",
                "category": "garbage",
                "description": "Massive overflow at dhalao near Ajmal Khan market spilling onto main vehicular lane.",
                "status": "TRIAGED",
                "severity": "P2",
                "latitude": 28.6502,
                "longitude": 77.1904,
                "ward_id": "MCD-54",
                "ward_name": "Karol Bagh",
                "city": "Delhi",
                "evidence_urls": ["https://images.unsplash.com/photo-1532996122724-e3c354a0b15b?w=800"],
                "poi_distance_m": 30.0,
                "poi_multiplier": 1.4,
                "sla_deadline": now + timedelta(hours=16),
                "upvotes": 8,
                "created_at": now - timedelta(hours=11)
            },
            {
                "id": "33333333-3333-3333-3333-333333333303",
                "category": "roads_potholes",
                "description": "Sunken road slab and deep fissure on Pusa Road near Sir Ganga Ram Hospital intersection.",
                "status": "IN_PROGRESS",
                "severity": "P1",
                "latitude": 28.6412,
                "longitude": 77.1805,
                "ward_id": "MCD-54",
                "ward_name": "Karol Bagh",
                "city": "Delhi",
                "evidence_urls": ["https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?w=800"],
                "poi_distance_m": 60.0,
                "poi_multiplier": 1.5,
                "sla_deadline": now + timedelta(hours=8),
                "assigned_to": "PWD Delhi Central Division",
                "upvotes": 11,
                "created_at": now - timedelta(hours=15)
            },
            {
                "id": "33333333-3333-3333-3333-333333333304",
                "category": "water",
                "description": "Sewage mixing with drinking water line reported in block 12A residential enclave.",
                "status": "ACKNOWLEDGED",
                "severity": "P1",
                "latitude": 28.6475,
                "longitude": 77.1860,
                "ward_id": "MCD-54",
                "ward_name": "Karol Bagh",
                "city": "Delhi",
                "evidence_urls": [],
                "poi_distance_m": 90.0,
                "poi_multiplier": 1.3,
                "sla_deadline": now + timedelta(hours=10),
                "upvotes": 6,
                "created_at": now - timedelta(hours=5)
            },
            {
                "id": "33333333-3333-3333-3333-333333333305",
                "category": "streetlights",
                "description": "Loose high voltage cable hanging near bus stop shelter on DB Gupta Road.",
                "status": "ASSIGNED",
                "severity": "P1",
                "latitude": 28.6515,
                "longitude": 77.1990,
                "ward_id": "MCD-54",
                "ward_name": "Karol Bagh",
                "city": "Delhi",
                "evidence_urls": [],
                "poi_distance_m": 45.0,
                "poi_multiplier": 1.5,
                "sla_deadline": now + timedelta(hours=4),
                "assigned_to": "Tata Power-DDL Emergency Response",
                "upvotes": 7,
                "created_at": now - timedelta(hours=6)
            },
            {
                "id": "33333333-3333-3333-3333-333333333306",
                "category": "roads_potholes",
                "description": "Broken sidewalk pavers and uneven surface outside Karol Bagh Metro Station Gate 2.",
                "status": "SUBMITTED",
                "severity": "P3",
                "latitude": 28.6448,
                "longitude": 77.1888,
                "ward_id": "MCD-54",
                "ward_name": "Karol Bagh",
                "city": "Delhi",
                "evidence_urls": [],
                "poi_distance_m": 15.0,
                "poi_multiplier": 1.5,
                "sla_deadline": now + timedelta(hours=48),
                "upvotes": 3,
                "created_at": now - timedelta(hours=1)
            }
        ]

        for rep in reports_seed:
            existing_r = db.query(Report).filter(Report.id == rep["id"]).first()
            if not existing_r:
                r_obj = Report(
                    id=rep["id"],
                    user_id=citizen_id,
                    category=rep["category"],
                    description=rep["description"],
                    status=rep["status"],
                    severity=rep["severity"],
                    latitude=rep["latitude"],
                    longitude=rep["longitude"],
                    ward_id=rep["ward_id"],
                    ward_name=rep["ward_name"],
                    city=rep["city"],
                    evidence_urls=rep.get("evidence_urls", []),
                    poi_distance_m=rep.get("poi_distance_m"),
                    poi_multiplier=rep.get("poi_multiplier", 1.0),
                    sla_deadline=rep.get("sla_deadline"),
                    assigned_to=rep.get("assigned_to"),
                    resolution_proof_url=rep.get("resolution_proof_url"),
                    resolution_notes=rep.get("resolution_notes"),
                    duplicate_of=rep.get("duplicate_of"),
                    upvotes=rep.get("upvotes", 1),
                    created_at=rep.get("created_at", now),
                    updated_at=rep.get("created_at", now)
                )
                db.add(r_obj)
                
                # Add initial CREATED event
                evt = ReportEvent(
                    id=str(uuid.uuid4()),
                    report_id=rep["id"],
                    event_type="CREATED",
                    payload={"category": rep["category"], "severity": rep["severity"]},
                    actor_role="citizen",
                    actor_id=citizen_id,
                    created_at=rep.get("created_at", now)
                )
                db.add(evt)
                print(f"Created report: {rep['id'][:8]} [{rep['ward_id']}] {rep['category']} ({rep['status']})")

        db.commit()

        # 5. SEED VERIFIABLE CRYPTOGRAPHIC RECEIPT FOR AGENT-FILED REPORT
        receipt_task_id = "task-bbmp-swd-2026-001"
        existing_rcpt = db.query(ReceiptModel).filter(ReceiptModel.task_id == receipt_task_id).first()
        if not existing_rcpt:
            receipt_payload = {
                "task_id": receipt_task_id,
                "report_id": agent_rep_id,
                "confirmation_number": "CPGRAMS-2026-B-891024",
                "portal_name": "CPGRAMS / BBMP Sahaaya",
                "applicant": "Aarav Sharma",
                "ward": "BBMP-151",
                "category": "drainage",
                "summary": "Stormwater drain blocked by construction debris",
                "submitted_at": (now - timedelta(hours=19)).isoformat()
            }
            genesis_hash = "0" * 64
            signed_obj = sign_receipt(receipt_payload, prev_hash=genesis_hash)
            
            rcpt_row = ReceiptModel(
                id=str(uuid.uuid4()),
                task_id=receipt_task_id,
                report_id=agent_rep_id,
                confirmation_number=receipt_payload["confirmation_number"],
                portal_name=receipt_payload["portal_name"],
                submitted_at=now - timedelta(hours=19),
                receipt_url=f"/receipts/{receipt_task_id}.pdf",
                signature=signed_obj["signature"],
                public_key=signed_obj["public_key"],
                prev_hash=signed_obj["prev_hash"],
                ticket_hash=signed_obj["ticket_hash"],
                payload=receipt_payload,
                created_at=now - timedelta(hours=19)
            )
            db.add(rcpt_row)
            db.commit()
            print(f"Created verifiable cryptographic receipt for task {receipt_task_id} with hash {signed_obj['ticket_hash'][:16]}...")
        else:
            print("Receipt already seeded.")

        print("Database seeding completed successfully.")

    except Exception as e:
        db.rollback()
        print("Error during database seed:", type(e), e)
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
