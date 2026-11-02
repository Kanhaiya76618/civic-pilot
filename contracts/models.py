"""
Swayam-sevak Data Contracts (Pydantic Models)
Standardized request/response models used across Server, Triage, and Agent layers.
"""

from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field

# User Roles
UserRole = Literal["citizen", "admin"]
ReportStatus = Literal["SUBMITTED", "TRIAGED", "ACKNOWLEDGED", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "REJECTED"]
ReportSeverity = Literal["P1", "P2", "P3", "P4"]
ReportCategory = Literal["roads_potholes", "garbage", "water", "streetlights", "drainage", "other"]

# ----------------- Auth Contracts -----------------

class UserBase(BaseModel):
    email: str
    name: Optional[str] = None
    role: UserRole = "citizen"

class UserCreate(UserBase):
    pass

class UserRead(UserBase):
    id: str
    created_at: datetime
    model_config = {"from_attributes": True}

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead

class LoginRequest(BaseModel):
    email: str
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)

class SignupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    email: str
    password: str = Field(..., min_length=8, max_length=128)
    officer_code: Optional[str] = Field(None, max_length=200)  # municipal access code: creates an officer account

# ----------------- Civic guide (official-source grounded chat) -----------------

class CivicGuideRequest(BaseModel):
    message: str = Field(..., min_length=12, max_length=1200)
    language: str = Field(default="English", min_length=2, max_length=30)
    scope: Literal["auto", "civic", "portal"] = "auto"

class CivicGuideSource(BaseModel):
    title: str
    url: str
    excerpt: str

class CivicGuideAction(BaseModel):
    label: str
    path: str

class CivicGuideSupport(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    url: Optional[str] = None

class CivicGuideResponse(BaseModel):
    answer: str
    category: str
    disclaimer: str
    sources: List[CivicGuideSource] = Field(default_factory=list)
    retrieval_status: str
    mode: Literal["civic", "portal"] = "civic"
    actions: List[CivicGuideAction] = Field(default_factory=list)
    support: Optional[CivicGuideSupport] = None

# ----------------- Grievance / Report Contracts -----------------

class CivicReportCreate(BaseModel):
    category: ReportCategory
    description: str = Field(..., min_length=5, max_length=2000)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    ward_id: Optional[str] = None
    city: Optional[str] = None
    evidence_urls: List[str] = Field(default_factory=list)

class CivicReportUpdate(BaseModel):
    status: Optional[ReportStatus] = None
    severity: Optional[ReportSeverity] = None
    assigned_to: Optional[str] = None
    resolution_proof_url: Optional[str] = None
    resolution_notes: Optional[str] = None

class ReportEventRead(BaseModel):
    id: str
    report_id: str
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    actor_role: str
    actor_id: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}

class CivicReportRead(BaseModel):
    id: str
    user_id: Optional[str] = None
    category: ReportCategory
    description: str
    status: ReportStatus
    severity: ReportSeverity
    latitude: float
    longitude: float
    ward_id: str
    ward_name: Optional[str] = None
    city: str
    evidence_urls: List[str] = Field(default_factory=list)
    poi_distance_m: Optional[float] = None
    poi_multiplier: float = 1.0
    sla_deadline: Optional[datetime] = None
    assigned_to: Optional[str] = None
    resolution_proof_url: Optional[str] = None
    resolution_notes: Optional[str] = None
    duplicate_of: Optional[str] = None
    upvotes: int = 1
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

# ----------------- Triage / Perception Contracts -----------------

class PerceptionAssessment(BaseModel):
    pothole_detected: bool = False
    pothole_confidence: float = 0.0
    crack_percentage: float = 0.0
    blur_score: float = 0.0
    is_blurry: bool = False
    transcription: Optional[str] = None
    detected_category: Optional[ReportCategory] = None
    detected_urgency: Optional[str] = None

class TriageResult(BaseModel):
    assigned_ward_id: str
    assigned_ward_name: str
    city: str
    computed_severity: ReportSeverity
    sla_hours: int
    poi_multiplier: float
    nearest_poi: Optional[str] = None
    nearest_poi_distance_m: Optional[float] = None
    duplicate_report_id: Optional[str] = None
    perception: Optional[PerceptionAssessment] = None

# ----------------- Receipt / Hash-Chain Contracts -----------------

class ReceiptRead(BaseModel):
    id: str
    task_id: str
    report_id: Optional[str] = None
    confirmation_number: str
    portal_name: str
    submitted_at: datetime
    receipt_url: Optional[str] = None
    signature: str
    public_key: str
    prev_hash: str
    ticket_hash: str
    payload: Dict[str, Any]
    created_at: datetime
    model_config = {"from_attributes": True}

class ReceiptVerifyRequest(BaseModel):
    receipt_data: Dict[str, Any]
    expected_prev_hash: Optional[str] = None

class ReceiptVerifyResponse(BaseModel):
    valid: bool
    message: str
    computed_ticket_hash: Optional[str] = None

# ----------------- Scheme Explainer Contracts -----------------

class SchemeRead(BaseModel):
    id: str
    scheme_code: str
    name: str
    ministry: str
    description: str
    eligibility_criteria: Dict[str, Any]
    benefits: str
    application_url: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}

class SchemeEligibilityQuery(BaseModel):
    income: Optional[float] = None
    location_type: Optional[str] = "urban"  # "urban" or "rural"
    occupation: Optional[str] = None
    has_ration_card: Optional[bool] = None
    own_pucca_house: Optional[bool] = None
    query_text: Optional[str] = None
    language: Optional[str] = "en"  # "en", "hi", "kn", "mr"

class SchemeEligibilityMatch(BaseModel):
    scheme: SchemeRead
    eligible: bool
    match_score: float
    reasons: List[str]
    missing_criteria: List[str]
