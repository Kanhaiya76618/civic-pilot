# 🏛️ CivicPilot: Autonomous Multimodal Vision, Audio & GIS Triage Engine (`2-CV`)

> **Comprehensive Developer, AI Agent & API Specification Document**  
> *Engineered for human engineers and autonomous AI coding agents (Antigravity, Cursor, Claude Code, Devin) for end-to-end perception, validation, municipal routing, and backend integration.*

---

## 🧭 1. System Overview & Architecture

`2-CV` is an open-source, AI-driven **Transparent Civic Grievance & Infrastructure Triage Engine**. It autonomously ingests raw citizen inputs (photos, voice notes, written statements, real-time GPS coordinates), filters spam, quantifies structural damage, performs geospatial point-in-polygon resolution, detects duplicate claims to block contractor fraud, and enforces legally binding response SLAs.

```
                              [CITIZEN MULTIMODAL INPUTS]
         ┌───────────────────────────────┼───────────────────────────────┐
         ▼                               ▼                               ▼
  📸 Damage Photo                 🎙️ Voice Audio / Text           📍 Real-Time GPS
(JPEG/PNG, Camera/Upload)         (MP3/WAV/M4A, Speech/Text)     (Browser Chip / Drag Pin)
         │                               │                               │
         ▼                               ▼                               ▼
  [GATE 1: SPAM FILTER]           [GATE 3: SPEECH NLP]           [GATE 4: VECTOR GIS]
  YOLOv8-Cls (ImageNet)          Whisper-Tiny + Lexicons         Shapely PIP (243 Wards)
  Rejects food/pets/memes        Extracts Intent & Distress      50m Haversine Deduplicator
         │ Passed                        │                               │
         ▼                               ▼                               ▼
  [GATE 2: DAMAGE QUANTIFIER]     [DEPARTMENTAL ROUTING]          [OFFICIAL & POI RESOLUTION]
  • YOLOv8 Pothole (conf=0.38)    PWD Roads / Bridges /           Identifies Zonal Engineer &
  • Bilateral Crack Morphology    BWSSB Water / Health SWM        Schools/Hospitals Multiplier
         │                               │                               │
         └───────────────────────────────┼───────────────────────────────┘
                                         ▼
                     [AUTONOMOUS TRIAGE SYNTHESIS ENGINE]
                         • Unified Severity Score (0–100)
                         • Statutory SLA (2h / 24h / 72h / 168h)
                         • Fraud / Duplicate Billing Prevention
                                         │
                                         ▼
                     [IMMUTABLE PUBLIC ACCOUNTABILITY LEDGER]
                         • Before vs. After Photographic Proof
                         • Citizen Dispute & Penalty Escalation Mechanism
```

---

## ✨ 2. Complete Features List

### A. Citizen Ingestion & Evidence Capture
* **Multimodal Ingestion**: Supports photo evidence, audio helpline recordings, written complaints, or any combination.
* **Smart Dataset Benchmark Explorer**: Integrated explorer for the 712-image benchmark dataset (Anant Singh Potholes & Plain Roads) and preloaded real-world municipal samples.
* **Written Statement NLP**: Citizens can type natural language statements with automatic entity and emergency intent extraction.

### B. Real-Time Geolocation & Interactive Map
* **Zero Dummy / Prefilled Data**: Does not assume or prefill fake coordinates or fake wards.
* **Hardware GPS Auto-Acquisition**: Browser queries `navigator.geolocation.getCurrentPosition()` with high-accuracy mode on page load.
* **Always-Visible Leaflet Map**: Standalone interactive street map powered by OpenStreetMap (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`) with **zero API keys required**.
* **True Drag-and-Drop Pin**: Citizens can drag the red SVG pin or click anywhere on the street to pinpoint defects with sub-meter precision.
* **"🎯 My Current GPS" Button**: Instant one-click re-centering to live hardware coordinates.
* **Client-Side Reverse Geocoding**: Queries OpenStreetMap Nominatim directly in the browser to resolve real locality, district, and municipal corporation names (e.g. *Hubballi-Dharwad Municipal Corporation (HDMC)*).

### C. Automated Geospatial Triage & Deduplication
* **Vector Point-in-Polygon (PIP)**: Shapely ray-casting resolves municipal boundaries across 243 Bangalore BBMP wards, Pune PMC wards, and dynamic urban jurisdictions in **$< 3\text{ ms}$**.
* **50-Meter Spatial Deduplication**: Haversine distance clustering automatically merges duplicate citizen reports within 50m of an active issue, upvoting existing tickets and preventing duplicate contractor billing.
* **Critical POI Proximity Escalation**: Automatically checks distance to critical infrastructure (trauma hospitals, school zones, metro stations within 500m) and applies priority boost multipliers ($1.2\times$ to $1.6\times$).

### D. Multi-Gate AI Perception & Fraud Prevention
* **Gate 1 Anti-Spam Gatekeeper**: Rejects non-civic imagery (pets, food, screenshots, memes) with 0 severity and a clear explanation.
* **Gate 2A Pothole Detection**: Custom-calibrated YOLOv8 model localized to asphalt craters with surface coverage percentage.
* **Gate 2B Structural Concrete Crack Analyzer**: Morphological black top-hat and bilateral filtering detects fine bridge, pier, and concrete cracks while rejecting shadow artifacts.
* **Gate 3 Speech-to-Text & Urgency Extraction**: Offline Whisper speech transcription with keyword matching for immediate life-safety hazards.

### E. Public Accountability & Repair Tracker
* **Cryptographic Audit Ledger**: Every complaint is assigned a SHA-256 hash-backed Ticket ID (`CIV-2026-{WARD}-{HASH}`).
* **Photographic Proof of Repair**: Displays Before vs. After repair images for public review.
* **"🚨 Dispute Repair (Fake / Poor Fix)"**: Citizens can reject substandard or fabricated repairs, immediately re-opening the ticket, resetting the countdown SLA, and flagging the contractor for municipal audit.

---

## 🧠 3. Machine Learning Models & Computer Vision Algorithms

| Subsystem | Model / Algorithm | Weight / Architecture | Primary Role |
| :--- | :--- | :--- | :--- |
| **Gate 1: Anti-Spam** | `yolov8n-cls.pt` | Ultralytics ImageNet-1k Classifier | Filters non-civic out-of-distribution uploads (food, animals, memes) |
| **Gate 2A: Potholes** | `pothole_best.pt` | YOLOv8 Object Detection (22.5 MB) | Localizes asphalt craters; calibrated confidence cutoff: `conf=0.38` |
| **Gate 2B: Structural Cracks** | Bilateral Top-Hat Morphology | Pure OpenCV Pipeline | Detects concrete fissures (`d=5, sigmaColor=30`, `aspect_ratio > 1.8`, `thinness > 14`) |
| **Gate 3: Speech ASR** | `openai/whisper-tiny` | PyTorch Transformers (39M params) | Universal offline audio transcription to 16kHz float32 mono |
| **Gate 3: Intent NLP** | Rule-Based Lexicon Classifier | `CIVIC_CATEGORIES` & indicators | Maps distress keywords to responsible municipal agencies and base severities |
| **Gate 4: GIS Boundaries** | Shapely Ray-Casting PIP | Vector MultiPolygons (GeoJSON) | Point-in-Polygon administrative ward and nodal engineer assignment |

---

## 🔌 4. APIs & Libraries Used

### External Web Services & APIs (Zero Commercial Keys Required)
* **OpenStreetMap Tile Service**: `https://tile.openstreetmap.org/{z}/{x}/{y}.png` (Free, public, zero API key).
* **OpenStreetMap Nominatim Reverse Geocoding**: `https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}` (Free, public client-side lookup).
* **HTML5 Geolocation API**: `navigator.geolocation.getCurrentPosition()` (Direct device hardware GPS).

### Core Python Libraries
* **Neural Networks & Inference**: `torch`, `torchvision`, `transformers`, `ultralytics`.
* **Audio Container Decoding**: `av` (PyAV) for in-memory audio decoding without FFmpeg binary installation.
* **Computer Vision**: `opencv-python` (`cv2`), `numpy`, `Pillow` (`PIL`).
* **Geospatial & Vector Math**: `shapely` (`Point`, `Polygon`, `MultiPolygon`).
* **Interactive UI**: `streamlit` (v1.25+), `streamlit.components.v1`.
* **Cryptography & Data Storage**: `hashlib`, `json`.

---

## 📥 5. Input Formats

### 1. Photo Evidence (`image`)
* **Supported Formats**: JPEG (`.jpg`, `.jpeg`), PNG (`.png`).
* **Resolution**: Any resolution (automatically resized to $640\times640$ maintaining aspect ratio for neural inference).
* **Metadata**: Optional EXIF geotagging (`GPSLatitude`, `GPSLongitude`) extracted if present.

### 2. Audio Evidence (`audio`)
* **Supported Formats**: MP3 (`.mp3`), WAV (`.wav`), M4A (`.m4a`), AAC (`.aac`), OGG (`.ogg`).
* **Decoding**: PyAV decodes in-memory to 16,000 Hz, 1-channel (mono), 32-bit floating-point arrays.

### 3. Written Complaint Statement (`complaint_text`)
* **Supported Formats**: Natural language UTF-8 string.
* **Example**: `"Huge crater pothole outside the school gate causing two-wheeler accidents."`

### 4. Geolocation (`lat`, `lon`)
* **Format**: WGS84 Decimal Degrees (`float`).
* **Latitude Range**: $-90.0$ to $+90.0$.
* **Longitude Range**: $-180.0$ to $+180.0$.
* **Accuracy**: Rounded to 5 decimal places ($\approx 1.1\text{ m}$ accuracy on Earth).

---

## 📤 6. Output Formats & Schemas

### A. Vision Perception Output (`src/vision_triage.py`)
```json
{
  "image_filename": "road_damage_01.jpg",
  "annotated_image_path": "data/ai_datasets/vision_damage/triage_annotated_road_damage_01.jpg",
  "status": "TRIAGED_AND_DISPATCHED",
  "is_valid_civic_infrastructure": true,
  "category_hint": "road",
  "severity_score": 91,
  "severity_level": "CRITICAL (STRUCTURAL HAZARD)",
  "damage_surface_coverage_pct": 3.07,
  "defect_count": 6,
  "recommended_sla_hours": 2,
  "detected_defects": [
    {
      "label": "Pothole Crater",
      "confidence": 0.42,
      "bbox": [142, 155, 266, 198],
      "area_pct": 1.74
    },
    {
      "label": "Structural Concrete Crack",
      "confidence": 0.95,
      "bbox": [344, 657, 416, 692],
      "area_pct": 0.82,
      "fissure_length_px": 296.5
    }
  ]
}
```

*When Gate 1 rejects non-infrastructure imagery:*
```json
{
  "image_filename": "burger.jpg",
  "status": "REJECTED_AS_SPAM",
  "is_valid_civic_infrastructure": false,
  "severity_score": 0,
  "rejection_reason": "Gate 1 rejected: 'cheeseburger' (confidence: 96.2%) is not civic infrastructure.",
  "detected_defects": []
}
```

---

### B. Audio & Text Intent Output (`src/audio_triage.py`)
```json
{
  "audio_filename": "voice_call.mp3",
  "transcript": "A major underground water pipe has burst on 100 Feet Road... flooding the entire junction.",
  "category": "WATER_AND_DRAINAGE",
  "severity_score": 85,
  "priority_label": "CRITICAL (LIFE-SAFETY HAZARD)",
  "enforced_sla_hours": 2,
  "sla_tier": "CRITICAL_IMMEDIATE",
  "primary_department": "Water Supply & Sewerage Board (BWSSB / Jal Board)",
  "secondary_department": "Roads & Infrastructure (Pavement Erosion)",
  "emergency_keywords_detected": [],
  "urgency_keywords_detected": ["flooding", "washing away", "immediate", "burst", "high pressure"],
  "extracted_locations": ["100 Feet Road", "The Metro Station"],
  "audit_ledger_status": "VOICE_VERIFIED_AND_DISPATCHED"
}
```

---

### C. Geospatial PIP & Deduplication Output (`src/gis_routing.py`)

#### Ward Resolution:
```json
{
  "latitude": 15.39353,
  "longitude": 75.02489,
  "city": "Hubballi-Dharwad Municipal Corporation (HDMC)",
  "ward_name": "Hubballi-Dharwad Urban Jurisdiction",
  "ward_number": "HDMC-Live",
  "ward_id": "GPS-15393",
  "executive_engineer_in_charge": "AEE - Hubballi-Dharwad City Division",
  "control_room_hotline": "+91-80-2222-1188",
  "nearby_critical_pois": [],
  "poi_vulnerability_multiplier": 1.0
}
```

#### 50m Spatial Deduplication:
```json
{
  "is_duplicate": true,
  "action": "MERGE_AND_UPVOTE",
  "matched_parent_ticket": "CIV-2026-121-7F83B165",
  "distance_meters": 14.8,
  "cluster_status": "DISPATCHED_TO_CREW",
  "total_citizen_reports": 4,
  "explanation": "Duplicate incident detected within 14.8m of active ticket #CIV-2026-121-7F83B165. Auto-merged to prevent redundant contractor billing."
}
```

---

### D. Canonical Public Ledger Schema (`data/grievance_ledger.json`)

The final, unified ticket persisted for public transparency and downstream execution agents:

```json
{
  "ticket_id": "CIV-2026-HDMC-Live-93B41C02",
  "title": "Incident in Hubballi-Dharwad Urban Jurisdiction",
  "description": "Severe deep crater pothole near bus terminal causing accidents.",
  "category": "ROADS_AND_PAVEMENTS",
  "ward_name": "Hubballi-Dharwad Urban Jurisdiction",
  "ward_no": "HDMC-Live",
  "engineer": "AEE - Hubballi-Dharwad City Division",
  "lat": 15.39353,
  "lon": 75.02489,
  "severity_score": 92,
  "status": "DISPATCHED_TO_CONTRACTOR",
  "reported_at": "Just now (Live)",
  "sla_target": "2 Hours",
  "resolved_in": "Active countdown",
  "before_image": "damage_crater_01.jpg",
  "after_image": null,
  "disputed": false,
  "dispute_count": 0
}
```

---

## 🚀 7. FastAPI Gateway Blueprint (For Backend Integration)

Autonomous agents or backend microservices can expose this subsystem as a REST service:

```python
from fastapi import FastAPI, UploadFile, File, Form
from src.vision_triage import CivicVisionTriageEngine
from src.audio_triage import CivicAudioTriageEngine
from src.gis_routing import CivicGISRouter
import shutil, os

app = FastAPI(title="CivicPilot Triage Gateway", version="2.0.0")

vision_engine = CivicVisionTriageEngine("pothole_best.pt")
audio_engine = CivicAudioTriageEngine()
gis_router = CivicGISRouter()

@app.post("/api/v1/triage")
async def triage_grievance(
    lat: float = Form(...),
    lon: float = Form(...),
    complaint_text: str = Form(None),
    custom_address: str = Form(None),
    image: UploadFile = File(None),
    audio: UploadFile = File(None)
):
    # 1. Geospatial Resolution & Deduplication
    ward_info = gis_router.resolve_location(lat, lon, custom_address=custom_address)
    dup_info = gis_router.check_spatial_duplicate(lat, lon, "Civic Defect")
    
    # 2. Vision Perception
    vision_res = None
    if image:
        temp_img = f"/tmp/{image.filename}"
        with open(temp_img, "wb") as f:
            shutil.copyfileobj(image.file, f)
        vision_res = vision_engine.analyze_image(temp_img)
        
    # 3. Audio / Text Intent
    audio_res = None
    if audio:
        temp_aud = f"/tmp/{audio.filename}"
        with open(temp_aud, "wb") as f:
            shutil.copyfileobj(audio.file, f)
        audio_res = audio_engine.analyze_audio_report(temp_aud)
    elif complaint_text:
        audio_res = audio_engine.analyze_text_report(complaint_text)

    # 4. Severity & SLA Synthesis
    scores = []
    if vision_res and vision_res.get("is_valid_civic_infrastructure", True):
        scores.append(vision_res["severity_score"])
    if audio_res:
        scores.append(audio_res["severity_score"])
    final_score = max(scores) if scores else 40

    if ward_info.get("poi_vulnerability_multiplier", 1.0) > 1.0:
        final_score = min(99, int(final_score * ward_info["poi_vulnerability_multiplier"]))

    sla_hours = 2 if final_score >= 80 else (24 if final_score >= 60 else (72 if final_score >= 40 else 168))
    
    return {
        "status": "TRIAGED_AND_DISPATCHED",
        "severity_score": final_score,
        "enforced_sla_hours": sla_hours,
        "ward": ward_info,
        "deduplication": dup_info,
        "vision": vision_res,
        "audio": audio_res
    }
```

---

## 💻 8. Quickstart & Verification

```bash
# 1. Clone Branch
git clone -b 2-CV https://github.com/Kanhaiya76618/civic-pilot.git
cd civic-pilot

# 2. Install Python Dependencies
pip install -r requirements.txt

# 3. Launch Interactive Demonstration
streamlit run src/app_demo.py --server.port 8501
```

* Open your browser at `http://localhost:8501`.
* **Tab 1: 📝 File Civic Grievance**: Upload damage photos, voice calls, write statements, and view the real-time device GPS interactive map.
* **Tab 2: 🔍 Public Transparency Ledger**: Inspect all triaged work orders, Before vs. After repair images, and test the Citizen Dispute / Re-complaint mechanism.
