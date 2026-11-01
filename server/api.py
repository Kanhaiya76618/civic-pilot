"""
Swayam-sevak Unified API Router
Unifies:
- Auth & Roles (Citizen, Municipal Admin)
- Grievance Intake & Triage (Part 2)
- Municipal Admin Desk (Part 2 Admin surface)
- Public Accountability Board & Live Stats
- Verifiable Receipts & Cryptographic Ledger
- Scheme Explainer & Eligibility Matching (Part 1)
- AutoFile Escalation (Part 2 -> Part 3 bridge)
"""

import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from server.db import (
    get_db, User, Report, ReportEvent, ReceiptModel, Scheme, PortalRegistry
)
from server.auth import (
    create_access_token, get_current_user, require_role
)
from fastapi.responses import Response
from server.storage import upload_evidence, validate_file, StorageValidationError, storage_path_of, read_evidence
from server.triage import compute_triage_decision
from server.receipts import sign_receipt, verify_receipt
from contracts.models import (
    UserRead, TokenResponse, LoginRequest, SignupRequest, CivicReportRead,
    CivicReportCreate, ReportEventRead, ReceiptRead, ReceiptVerifyRequest,
    ReceiptVerifyResponse, SchemeRead, SchemeEligibilityQuery, SchemeEligibilityMatch,
    CivicGuideRequest, CivicGuideResponse
)
from server.civic_guide import CivicGuide, GuideUnavailable

router = APIRouter()
_civic_guide = CivicGuide()

# ==============================================================================
# 1. AUTHENTICATION & DEMO ROLES
# ==============================================================================

DEMO_IDENTITIES = {
    "citizen@demo.in": ("Aarav Sharma", "citizen"),
    "admin@demo.in": ("Priya Nair (Municipal Desk Admin)", "admin"),
}

def _app_token_response(user: User) -> JSONResponse:
    """Issue Swayam-sevak's short-lived app token after Supabase has authenticated a user."""
    token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role})
    response = JSONResponse(content={
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "created_at": user.created_at.isoformat()
        }
    })
    # Set httpOnly cookie for web client
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=86400 * 7, samesite="lax")
    return response

def _supabase_auth_client():
    """Use the publishable key for end-user credentials; keep the service key out of this path."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY")
    if not url or not key:
        raise HTTPException(status_code=503, detail="Supabase Auth is not configured. Add SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY.")
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Supabase Auth is unavailable. Please try again shortly.") from exc

def _profile_name(auth_user: Any, fallback: Optional[str] = None) -> str:
    metadata = getattr(auth_user, "user_metadata", None) or {}
    return str(metadata.get("name") or fallback or "Citizen User").strip()[:80]

def _profile_role(auth_user: Any) -> str:
    """Read a role only from trusted Supabase app metadata, never user-editable metadata."""
    metadata = getattr(auth_user, "app_metadata", None) or {}
    return "admin" if metadata.get("civic_role") == "admin" else "citizen"

def _sync_authenticated_user(db: Session, email: str, name: Optional[str], trusted_role: str = "citizen") -> User:
    """Mirror a verified Supabase identity; only server-managed app metadata may grant admin access."""
    user = db.query(User).filter(User.email == email).first()
    if user:
        changed = False
        if name and user.name != name:
            user.name = name
            changed = True
        if trusted_role == "admin" and user.role != "admin":
            user.role = "admin"
            changed = True
        if changed:
            db.commit()
            db.refresh(user)
        return user
    user = User(
        id=str(uuid.uuid4()), email=email, name=name or "Citizen User", role=trusted_role,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def _legacy_demo_login(db: Session, email: str) -> JSONResponse:
    """Compatibility bridge for the seeded test accounts only; the web UI never calls this path."""
    name, role = DEMO_IDENTITIES[email]
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(id=str(uuid.uuid4()), email=email, name=name, role=role, created_at=datetime.now(timezone.utc))
        db.add(user)
        db.commit()
        db.refresh(user)
    return _app_token_response(user)

@router.post("/api/v1/auth/signup")
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    """Create a citizen identity in Supabase Auth. Municipal roles are provisioned, never self-selected."""
    email = req.email.strip().lower()
    client = _supabase_auth_client()
    redirect_to = f"{os.getenv('CIVIC_PUBLIC_URL', 'http://localhost:5173').rstrip('/')}/signin?confirmed=1"
    try:
        result = client.auth.sign_up({
            "email": email,
            "password": req.password,
            "options": {"data": {"name": req.name.strip()}, "email_redirect_to": redirect_to},
        })
    except Exception as exc:
        message = str(exc)
        if "already" in message.lower():
            message = "An account may already exist for this email. Try signing in or check your inbox."
        raise HTTPException(status_code=400, detail=message) from exc

    # Hosted Supabase projects normally require email confirmation. Do not mint a local session first.
    if not getattr(result, "session", None):
        return JSONResponse(status_code=202, content={
            "status": "confirmation_required",
            "message": "Check your inbox to confirm your email, then return here to sign in.",
        })
    user = _sync_authenticated_user(db, email, req.name.strip())
    return _app_token_response(user)

@router.post("/api/v1/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Password sign-in through Supabase Auth; the local user row controls civic authorization only."""
    email = req.email.strip().lower()
    # Existing automated tests and seeded local demo remain usable, but the browser UI always submits a password.
    if not req.password:
        # Password-less demo accounts exist for automated tests only. Without this switch (never set in a
        # deployment) nobody can sign in as citizen@demo.in or the admin@demo.in municipal desk without a password.
        if email in DEMO_IDENTITIES and os.environ.get("CIVIC_ALLOW_DEMO_LOGIN") == "1":
            return _legacy_demo_login(db, email)
        raise HTTPException(status_code=422, detail="Password is required. Create an account if you are new to Swayam-sevak.")
    client = _supabase_auth_client()
    try:
        result = client.auth.sign_in_with_password({"email": email, "password": req.password})
    except Exception as exc:
        # Keep failed-login feedback generic so account existence is not disclosed.
        raise HTTPException(status_code=401, detail="Email or password is incorrect. Please try again.") from exc
    auth_user = getattr(result, "user", None)
    if not auth_user or not getattr(auth_user, "email", None):
        raise HTTPException(status_code=401, detail="Email or password is incorrect. Please try again.")
    user = _sync_authenticated_user(
        db,
        auth_user.email.strip().lower(),
        _profile_name(auth_user),
        _profile_role(auth_user),
    )
    return _app_token_response(user)


@router.get("/api/v1/auth/me", response_model=UserRead)
async def get_me(user: Optional[User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# ==============================================================================
# 1B. OFFICIAL-SOURCE CIVIC GUIDE
# ==============================================================================

@router.post("/api/v1/civic-guide/chat", response_model=CivicGuideResponse)
async def civic_guide_chat(
    request: CivicGuideRequest,
    user: User = Depends(require_role(["citizen", "admin"])),
):
    """Answer only after retrieving official Indian-government/regulator sources."""
    try:
        return await _civic_guide.answer(request.message, request.language, request.scope)
    except GuideUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ==============================================================================
# 2. CITIZEN GRIEVANCE INTAKE & PERCEPTION TRIAGE (Part 2)
# ==============================================================================

@router.post("/api/reports")
@router.post("/api/v1/reports")
@router.post("/app/part2/api/reports")
async def create_and_triage_report(
    category: str = Form("other"),
    description: str = Form(""),
    latitude: float = Form(...),
    longitude: float = Form(...),
    photo: Optional[UploadFile] = File(None),
    voice: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["citizen"]))
):
    """
    Multimodal grievance intake with automated AI triage:
    - Runs CV (YOLO pothole, crack morphology, blur detection)
    - GIS Ward mapping & POI proximity multiplier (1.2 - 1.6x)
    - 50-meter spatial deduplication (merge & upvote)
    - SLA deadline computation
    """
    report_id = str(uuid.uuid4())
    evidence_urls = []
    photo_bytes = None

    # Handle Photo Upload
    if photo:
        photo_bytes = await photo.read()
        if len(photo_bytes) > 0:
            try:
                upload_res = upload_evidence(
                    file_bytes=photo_bytes,
                    filename=photo.filename or "evidence.jpg",
                    content_type=photo.content_type or "image/jpeg",
                    report_id=report_id
                )
                evidence_urls.append(upload_res["ref"])
            except StorageValidationError as e:
                raise HTTPException(status_code=e.status_code, detail=e.message)

    # Handle Voice Upload
    if voice:
        voice_bytes = await voice.read()
        if len(voice_bytes) > 0:
            try:
                # Store voice note
                media = (voice.content_type or "audio/webm").split(";")[0].strip()
                ext = {"audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mpeg": ".mp3", "audio/mp4": ".m4a"}.get(media, ".webm")
                v_res = upload_evidence(
                    file_bytes=voice_bytes,
                    filename=f"voice{ext}",  # its real type: it was sent as a PDF before and always rejected
                    content_type=media,
                    report_id=report_id
                )
                evidence_urls.append(v_res["ref"])
            except StorageValidationError as e:
                raise HTTPException(status_code=e.status_code, detail=f"Voice note: {e.message}")

    # Run AI Triage Engine
    triage = compute_triage_decision(
        category=category,
        description=description,
        lat=latitude,
        lng=longitude,
        image_bytes=photo_bytes,
        db=db
    )

    user_id = user.id if user else None
    now = datetime.now(timezone.utc)

    # Check if duplicate
    dup_id = triage.get("duplicate_of")
    if dup_id:
        parent_report = db.query(Report).filter(Report.id == dup_id).first()
        if parent_report:
            parent_report.upvotes = (parent_report.upvotes or 1) + 1
            db.commit()

    report = Report(
        id=report_id,
        user_id=user_id,
        category=triage["category"],
        description=description,
        status="TRIAGED",
        severity=triage["severity"],
        latitude=latitude,
        longitude=longitude,
        ward_id=triage["assigned_ward_id"],
        ward_name=triage["assigned_ward_name"],
        city=triage["city"],
        evidence_urls=evidence_urls,
        poi_distance_m=triage.get("nearest_poi_distance_m"),
        poi_multiplier=triage.get("poi_multiplier", 1.0),
        sla_deadline=triage.get("sla_deadline"),
        duplicate_of=dup_id,
        upvotes=1,
        created_at=now,
        updated_at=now
    )
    db.add(report)

    # Log Events
    evt_created = ReportEvent(
        id=str(uuid.uuid4()),
        report_id=report_id,
        event_type="CREATED",
        payload={"category": category, "description": description},
    actor_role=user.role,
        actor_id=user_id,
        created_at=now
    )
    evt_triaged = ReportEvent(
        id=str(uuid.uuid4()),
        report_id=report_id,
        event_type="TRIAGED",
        payload={
            "severity": triage["severity"],
            "ward_name": triage["assigned_ward_name"],
            "poi": triage.get("nearest_poi"),
            "duplicate_of": dup_id
        },
        actor_role="system",
        created_at=now
    )
    db.add(evt_created)
    db.add(evt_triaged)
    db.commit()

    return {
        "code": report.id,
        "id": report.id,
        "severity": report.severity,
        "category": report.category,
        "status": report.status,
        "ward_id": report.ward_id,
        "ward_name": report.ward_name,
        "city": report.city,
        "duplicate_of": report.duplicate_of,
        "sla_deadline": report.sla_deadline.isoformat() if report.sla_deadline else None,
        "reasoning": f"Assigned {report.severity} to {report.ward_name} with {report.poi_multiplier}x POI multiplier near {triage.get('nearest_poi') or 'civic zone'}.",
        "perception": triage.get("perception")
    }


@router.post("/api/reports/{id}/upvote")
async def upvote_report(id: str, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    report.upvotes = (report.upvotes or 1) + 1
    db.commit()
    return {"ok": True, "upvotes": report.upvotes}


@router.post("/api/reports/{id}/dispute")
async def dispute_report(
    id: str, 
    reason: str = Form("Issue not satisfactorily resolved"), 
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["citizen"]))
):
    """Citizen dispute-repair: reopens closed/dissatisfied report, resets SLA, flags for admin review."""
    report = db.query(Report).filter(Report.id == id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    report.status = "TRIAGED"
    # Reset SLA to 24h emergency window
    now = datetime.now(timezone.utc)
    report.sla_deadline = now + timedelta(hours=24)
    report.updated_at = now
    
    evt = ReportEvent(
        id=str(uuid.uuid4()),
        report_id=report.id,
        event_type="DISPUTED",
        payload={"reason": reason},
        actor_role=user.role,
        actor_id=user.id,
        created_at=now
    )
    db.add(evt)
    db.commit()
    return {"ok": True, "status": report.status, "message": "Report disputed and reopened for review."}


# ==============================================================================
# 3. PUBLIC ACCOUNTABILITY BOARD & STATS
# ==============================================================================

@router.get("/api/reports")
@router.get("/api/public/reports")
@router.get("/app/part2/api/public/reports")
async def get_public_reports(db: Session = Depends(get_db)):
    """Returns reports formatted for the public board and map visualization."""
    reports = db.query(Report).order_by(desc(Report.created_at)).limit(100).all()
    now = datetime.now(timezone.utc)
    
    formatted = []
    for r in reports:
        is_breached = bool(r.sla_deadline and r.sla_deadline < now and r.status != "RESOLVED")
        formatted.append({
            "code": str(r.id),
            "id": str(r.id),
            "lat": r.latitude,
            "lng": r.longitude,
            "severity": r.severity,
            "status": r.status.lower(),
            "category": r.category,
            "source": "citizen" if not r.receipts else "agent",
            "ward": r.ward_name or r.ward_id,
            "sla_breached": is_breached,
            "description": r.description,
            "upvotes": r.upvotes,
            "evidence_urls": [],  # citizens' own photos and voice notes are not public
            "evidence_count": len(r.evidence_urls or []),
            "resolution_proof_url": proof_link(r),
            "resolution_notes": r.resolution_notes,
            "duplicate_of": str(r.duplicate_of) if r.duplicate_of else None
        })
    return formatted


@router.get("/api/public/stats")
@router.get("/app/part2/api/public/stats")
async def get_public_stats(db: Session = Depends(get_db)):
    """Returns real aggregate metrics for the Public Board."""
    now = datetime.now(timezone.utc)
    reports = db.query(Report).all()
    
    total = len(reports)
    resolved = [r for r in reports if r.status == "RESOLVED"]
    resolved_pct = round((len(resolved) / total * 100), 1) if total > 0 else 0.0
    open_count = total - len(resolved)
    
    sla_breached = len([
        r for r in reports 
        if r.sla_deadline and r.sla_deadline < now and r.status != "RESOLVED"
    ])
    
    # Calculate average resolution time for resolved reports
    resolution_hours = []
    for r in resolved:
        diff = (r.updated_at - r.created_at).total_seconds() / 3600.0
        resolution_hours.append(max(1.0, diff))
    # No resolved reports yet: say so (null), never a made-up average.
    avg_hours = round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else None

    return {
        "total": total,
        "open": open_count,
        "resolved_pct": resolved_pct,
        "avg_resolution_hours": avg_hours,
        "sla_breached": sla_breached
    }


# ==============================================================================
# 4. MUNICIPAL ADMIN DESK (Part 2 Admin Surface)
# ==============================================================================

@router.get("/api/v1/admin/queue")
async def get_admin_queue(
    status_filter: Optional[str] = Query(None),
    ward_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(["admin"]))
):
    """
    Municipal Desk Triage Queue:
    Sorted by urgency: P1 emergency -> approaching/breached SLA -> P2 -> P3.
    """
    query = db.query(Report)
    if status_filter:
        query = query.filter(Report.status == status_filter.upper())
    if ward_filter:
        query = query.filter(Report.ward_id == ward_filter)

    reports = query.order_by(
        Report.severity.asc(),  # P1 before P2 before P3
        Report.sla_deadline.asc()
    ).all()

    now = datetime.now(timezone.utc)
    queue = []
    for r in reports:
        is_breached = bool(r.sla_deadline and r.sla_deadline < now and r.status != "RESOLVED")
        queue.append({
            "id": str(r.id),
            "category": r.category,
            "description": r.description,
            "severity": r.severity,
            "status": r.status,
            "ward_id": r.ward_id,
            "ward_name": r.ward_name,
            "city": r.city,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "sla_deadline": r.sla_deadline.isoformat() if r.sla_deadline else None,
            "sla_breached": is_breached,
            "poi_multiplier": r.poi_multiplier,
            "assigned_to": r.assigned_to,
            "upvotes": r.upvotes,
            "duplicate_of": str(r.duplicate_of) if r.duplicate_of else None,
            "evidence_urls": evidence_links(r),
            "resolution_proof_url": proof_link(r),
            "created_at": r.created_at.isoformat()
        })
    return queue


@router.post("/api/v1/admin/reports/{id}/triage")
async def admin_override_triage(
    id: str,
    category: Optional[str] = Form(None),
    severity: Optional[str] = Form(None),
    ward_id: Optional[str] = Form(None),
    notes: Optional[str] = Form(""),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(["admin"]))
):
    """Admin Accept or Override of AI suggestion."""
    report = db.query(Report).filter(Report.id == id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    now = datetime.now(timezone.utc)
    if category:
        report.category = category
    if severity:
        report.severity = severity
    if ward_id:
        report.ward_id = ward_id
    report.status = "TRIAGED"
    report.updated_at = now

    evt = ReportEvent(
        id=str(uuid.uuid4()),
        report_id=report.id,
        event_type="TRIAGED",
        payload={"admin_override": True, "notes": notes, "severity": report.severity},
        actor_role="admin",
        actor_id=admin_user.id,
        created_at=now
    )
    db.add(evt)
    db.commit()
    return {"ok": True, "report": {"id": report.id, "severity": report.severity, "status": report.status}}


@router.post("/api/v1/admin/reports/{id}/acknowledge")
async def admin_acknowledge_report(
    id: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(["admin"]))
):
    """Admin acknowledges report."""
    report = db.query(Report).filter(Report.id == id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    now = datetime.now(timezone.utc)
    report.status = "ACKNOWLEDGED"
    report.updated_at = now
    
    evt = ReportEvent(
        id=str(uuid.uuid4()),
        report_id=report.id,
        event_type="ACKNOWLEDGED",
        payload={},
        actor_role="admin",
        actor_id=admin_user.id,
        created_at=now
    )
    db.add(evt)
    db.commit()
    return {"ok": True, "status": report.status}


@router.post("/api/v1/admin/reports/{id}/assign")
async def admin_assign_report(
    id: str,
    assigned_to: str = Form(...),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(["admin"]))
):
    """Admin assigns report to contractor or division."""
    report = db.query(Report).filter(Report.id == id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    now = datetime.now(timezone.utc)
    report.assigned_to = assigned_to
    report.status = "ASSIGNED"
    report.updated_at = now
    
    evt = ReportEvent(
        id=str(uuid.uuid4()),
        report_id=report.id,
        event_type="ASSIGNED",
        payload={"assigned_to": assigned_to},
        actor_role="admin",
        actor_id=admin_user.id,
        created_at=now
    )
    db.add(evt)
    db.commit()
    return {"ok": True, "status": report.status, "assigned_to": report.assigned_to}


# ------------------------------------------------------------------ evidence delivery
# The bucket stays private. The database stores where a file is (evidence://report/file); this server fetches it with
# its own key. Proof-of-repair photos are public (that is the accountability). Citizens' photos and voice notes are
# for the municipal desk only.

def proof_link(r) -> str | None:
    return f"/api/v1/evidence/{r.id}/proof" if storage_path_of(r.resolution_proof_url) else None


def evidence_links(r) -> list[str]:
    return [f"/api/v1/evidence/{r.id}/{i}" for i, ref in enumerate(r.evidence_urls or []) if storage_path_of(ref)]


def _report_or_404(db: Session, report_id: str):
    try:
        uuid.UUID(report_id)  # anything else would crash the database query
    except ValueError:
        raise HTTPException(status_code=404, detail="Report not found")
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


def _serve(stored: str | None, what: str) -> Response:
    path = storage_path_of(stored)
    got = read_evidence(path) if path else None
    if not got:
        raise HTTPException(status_code=404, detail=f"{what} is not available in storage.")
    data, media = got
    return Response(data, media_type=media, headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"})


@router.get("/api/v1/evidence/{report_id}/proof")
async def evidence_proof(report_id: str, db: Session = Depends(get_db)):
    """Proof-of-repair photo: public, so anyone can check a 'resolved' claim."""
    return _serve(_report_or_404(db, report_id).resolution_proof_url, "The resolution proof photo")


@router.get("/api/v1/evidence/{report_id}/{index}")
async def evidence_item(report_id: str, index: int, db: Session = Depends(get_db),
                        admin_user: User = Depends(require_role(["admin"]))):
    """A citizen's photo or voice note: municipal desk only."""
    items = _report_or_404(db, report_id).evidence_urls or []
    if not 0 <= index < len(items):
        raise HTTPException(status_code=404, detail="Evidence not found")
    return _serve(items[index], "This evidence file")


@router.post("/api/v1/admin/reports/{id}/resolve")
async def admin_resolve_report(
    id: str,
    resolution_notes: str = Form(...),
    proof_photo: UploadFile = File(...),  # MANDATORY PROOF PHOTO
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(["admin"]))
):
    """
    Admin resolves report.
    Mandatory proof photo requirement prevents fraudulent contractor closure.
    """
    report = db.query(Report).filter(Report.id == id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    photo_bytes = await proof_photo.read()
    if not photo_bytes or len(photo_bytes) == 0:
        raise HTTPException(status_code=400, detail="Mandatory resolution proof photo is required to resolve a ticket.")

    try:
        upload_res = upload_evidence(
            file_bytes=photo_bytes,
            filename=proof_photo.filename or "resolution_proof.jpg",
            content_type=proof_photo.content_type or "image/jpeg",
            report_id=report.id
        )
    except StorageValidationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    now = datetime.now(timezone.utc)
    report.status = "RESOLVED"
    report.resolution_proof_url = upload_res["ref"]
    report.resolution_notes = resolution_notes
    report.updated_at = now

    evt = ReportEvent(
        id=str(uuid.uuid4()),
        report_id=report.id,
        event_type="RESOLVED",
        payload={
            "resolution_notes": resolution_notes,
            "proof_ref": upload_res["ref"]
        },
        actor_role="admin",
        actor_id=admin_user.id,
        created_at=now
    )
    db.add(evt)
    db.commit()
    return {
        "ok": True, 
        "status": report.status, 
        "resolution_proof_url": proof_link(report),
        "resolution_notes": report.resolution_notes
    }


# ==============================================================================
# 5. VERIFIABLE RECEIPTS & CRYPTOGRAPHIC LEDGER
# ==============================================================================

@router.get("/api/v1/receipts")
async def list_receipts(db: Session = Depends(get_db)):
    """Returns hash-chained cryptographic receipts."""
    receipts = db.query(ReceiptModel).order_by(ReceiptModel.submitted_at.desc()).all()
    return [
        {
            "id": str(r.id),
            "task_id": r.task_id,
            "report_id": str(r.report_id) if r.report_id else None,
            "confirmation_number": r.confirmation_number,
            "portal_name": r.portal_name,
            "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            "receipt_url": r.receipt_url,
            "signature": r.signature,
            "public_key": r.public_key,
            "prev_hash": r.prev_hash,
            "ticket_hash": r.ticket_hash,
            "payload": r.payload,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in receipts
    ]


@router.post("/api/v1/receipts/verify")
async def verify_receipt_endpoint(req: ReceiptVerifyRequest):
    """Cryptographically verifies Ed25519 signature and hash-chain integrity."""
    valid, message = verify_receipt(req.receipt_data, expected_prev_hash=req.expected_prev_hash)
    return {
        "valid": valid,
        "message": message,
        "meaning": "Tamper-evident cryptographic signature verified via Ed25519 authority" if valid else "Verification Failed"
    }


# ==============================================================================
# 6. WELFARE SCHEME EXPLAINER (Part 1)
# ==============================================================================

@router.get("/api/v1/schemes")
@router.get("/app/part1/schemes")
async def list_schemes(db: Session = Depends(get_db)):
    """Lists welfare schemes from knowledge base."""
    schemes = db.query(Scheme).all()
    return [
        {
            "id": str(s.id),
            "scheme_code": s.scheme_code,
            "name": s.name,
            "ministry": s.ministry,
            "description": s.description,
            "eligibility_criteria": s.eligibility_criteria,
            "benefits": s.benefits,
            "application_url": s.application_url,
            "created_at": s.created_at.isoformat() if s.created_at else None
        }
        for s in schemes
    ]


@router.post("/api/v1/schemes/match")
@router.post("/app/part1/match")
async def match_schemes(query: SchemeEligibilityQuery, db: Session = Depends(get_db)):
    """
    Evaluates citizen eligibility against welfare schemes.
    Provides multilingual justification.
    """
    schemes = db.query(Scheme).all()
    results = []

    for s in schemes:
        crit = s.eligibility_criteria or {}
        reasons = []
        missing = []
        is_eligible = True
        score = 0.5

        # Check income criteria
        if "income_limit" in crit and query.income is not None:
            if query.income <= crit["income_limit"]:
                reasons.append(f"Household income of ₹{int(query.income)} is below limit of ₹{int(crit['income_limit'])}")
                score += 0.3
            else:
                missing.append(f"Income ₹{int(query.income)} exceeds limit ₹{int(crit['income_limit'])}")
                is_eligible = False

        # Check urban/rural criteria
        if crit.get("urban_resident") and query.location_type:
            if query.location_type.lower() == "urban":
                reasons.append("Resides in urban municipal limits")
                score += 0.2
            else:
                missing.append("Requires urban residency")
                is_eligible = False

        # Check housing criteria
        if crit.get("no_pucca_house") and query.own_pucca_house is not None:
            if not query.own_pucca_house:
                reasons.append("Does not own a permanent pucca house")
                score += 0.2
            else:
                missing.append("Requires not owning a pucca house")
                is_eligible = False

        results.append({
            "scheme": {
                "id": str(s.id),
                "scheme_code": s.scheme_code,
                "name": s.name,
                "ministry": s.ministry,
                "description": s.description,
                "benefits": s.benefits,
                "application_url": s.application_url
            },
            "eligible": is_eligible,
            "match_score": min(1.0, round(score, 2)),
            "reasons": reasons if reasons else ["General criteria matched"],
            "missing_criteria": missing
        })

    results.sort(key=lambda x: (x["eligible"], x["match_score"]), reverse=True)
    return results


# ==============================================================================
# 7. CLOSED-LOOP AUTOFILE (Part 2 -> Part 3 bridge)
# ==============================================================================

@router.post("/api/v1/reports/{id}/autofile")
async def trigger_autofile(
    id: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(["admin"]))
):
    """
    Escalation for filing: the report is flagged for the Part 3 filing agent.

    Nothing is filed here and no confirmation number or "filed" receipt is created: a real filing happens only when
    the agent runs on a portal and a person approves the final page (that run issues its own signed receipt).
    """
    try:
        uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Report not found")
    report = db.query(Report).filter(Report.id == id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    now = datetime.now(timezone.utc)
    escalation_id = f"escalation-{(report.ward_id or 'ward').lower()}-{uuid.uuid4().hex[:6]}"
    report.status = "ASSIGNED"
    report.assigned_to = "Escalated for filing (filing agent, pending approval)"
    report.updated_at = now
    db.add(ReportEvent(
        id=str(uuid.uuid4()),
        report_id=report.id,
        event_type="ASSIGNED",
        payload={"escalation": True, "escalation_id": escalation_id, "filed": False},
        actor_role="admin",
        actor_id=admin_user.id,
        created_at=now
    ))
    db.commit()
    return {
        "ok": True,
        "escalation_id": escalation_id,
        "filed": False,
        "status": report.status,
        "message": "Escalated for filing. Nothing has been filed yet: the filing agent fills the portal and a person "
                   "approves the final page; that run issues the signed receipt."
    }
