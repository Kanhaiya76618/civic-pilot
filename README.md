# 🏛️ CivicPilot: Part 2 — Autonomous Multimodal Vision, Audio & GIS Triage Engine (`2-CV`)

> **Developer & Agent Specification Document**  
> *Designed for human software engineers and autonomous AI coding agents (Antigravity, Cursor, Claude Code, Devin) to enable seamless backend integration, contract compliance, and execution agent interoperability.*

---

## 🧭 Executive Architecture & Subsystem Boundary

`2-CV` represents the **Perception, Verification & Autonomous Triage Subsystem** of the CivicPilot platform. It ingests unvetted citizen reports (imagery, audio recordings, GPS points), runs multi-gate neural perception, performs geometric GIS validation, enforces statutory response SLAs, and outputs tamper-evident JSON work orders for downstream execution engines (e.g., `part3-execution-agent`).

```
[Citizen Inputs]
  ├── Photo (JPEG/PNG)  ──────► Gate 1: Spam / OOD Filter (ImageNet Classifier)
  │                                    │ Passed
  │                                    ▼
  │                             Gate 2: Damage Quantifier (YOLOv8 + Fissure CV)
  │                                    │
  ├── Voice Note (Audio) ─────► Gate 3: Whisper ASR + Distress NLP Classifier
  │                                    │
  └── GPS (Lat, Lon)    ──────► Gate 4: Shapely Vector PIP + 50m Spatial Deduplicator
                                       │
                                       ▼
                       [Unified Triage Engine Synthesis]
                                       │
                   ┌───────────────────┴───────────────────┐
                   ▼                                       ▼
       Autonomous Severity (0–100)           Deterministic Department Routing
       Enforced SLA (2h / 24h / 72h)         Nodal Engineer Liable (Ward Level)
                   │                                       │
                   └───────────────────┬───────────────────┘
                                       ▼
                   [Immutable Public Ledger Payload (JSON)]
                                       │
                                       ▼
               Downstream Execution (e.g., part3-execution-agent)
```

---

## 📦 Core Python APIs & Contracts

Downstream backend services or agents can import the triage engines directly as modular Python classes:

### 1. Vision Perception Engine (`src/vision_triage.py`)

```python
from src.vision_triage import CivicVisionTriageEngine

engine = CivicVisionTriageEngine(pothole_weights="pothole_best.pt")
result = engine.analyze_image("path/to/damage.jpg", category_hint="road")
```

#### Output Contract (`dict`):
```json
{
  "image_filename": "damage.jpg",
  "annotated_image_path": "path/to/triage_annotated_damage.jpg",
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
      "confidence": 0.386,
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

* **Gate 1 Rejection Protocol**: If non-civic imagery is ingested (food, pets, memes), `is_valid_civic_infrastructure` returns `false`, `severity_score` is `0`, and `status` is `"REJECTED_AS_SPAM"`.

---

### 2. Audio & Speech-to-Text Intent Engine (`src/audio_triage.py`)

Uses PyAV for universal in-memory decoding (MP3/WAV/M4A/AAC/OGG) without system FFmpeg, running `openai/whisper-tiny` via PyTorch CPU.

```python
from src.audio_triage import CivicAudioTriageEngine

audio_engine = CivicAudioTriageEngine()
audio_result = audio_engine.analyze_audio_report("path/to/voice_note.mp3")
```

#### Output Contract (`dict`):
```json
{
  "audio_filename": "voice_note.mp3",
  "transcript": "A major underground water pipe has burst on 100 Feet Road... flooding the street.",
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

### 3. Geospatial Point-in-Polygon & Spatial Deduplication (`src/gis_routing.py`)

Vector boundary indexing against **243 Bangalore BBMP Wards** and Pune PMC Wards with 50-meter Haversine proximity checks.

```python
from src.gis_routing import CivicGISRouter

gis = CivicGISRouter()

# 1. Point-in-Polygon Ward Resolution
ward_info = gis.resolve_location(lat=12.9716, lon=77.6412)

# 2. 50-Meter Proximity Deduplication
dup_status = gis.check_spatial_duplicate(lat=12.9717, lon=77.6411, hazard_type="Pothole")
```

#### Ward Resolution Contract:
```json
{
  "latitude": 12.9716,
  "longitude": 77.6412,
  "city": "Bengaluru (BBMP)",
  "ward_name": "Old Thippasandra",
  "ward_number": "121",
  "ward_id": 5118,
  "executive_engineer_in_charge": "EE-Ward-121 (Old Thippasandra)",
  "control_room_hotline": "+91-80-2222-1188",
  "nearby_critical_pois": [],
  "poi_vulnerability_multiplier": 1.0
}
```

#### Deduplication Contract:
```json
{
  "is_duplicate": true,
  "action": "MERGE_AND_UPVOTE",
  "matched_parent_ticket": "CIV-2026-ACTIVE-01",
  "distance_meters": 15.5,
  "cluster_status": "DISPATCHED_TO_CREW",
  "total_citizen_reports": 4,
  "explanation": "Duplicate incident detected within 15.5m of active ticket #CIV-2026-ACTIVE-01. Auto-merged to prevent redundant contractor billing."
}
```

---

## 🔒 Unified Work Order Schema (For Downstream Agents)

When an incident is fully triaged, `src/app_demo.py` persists this canonical record to `data/grievance_ledger.json`. Downstream execution agents should consume this exact schema:

```json
{
  "ticket_id": "CIV-2026-121-7F83B165",
  "status": "DISPATCHED_TO_CONTRACTOR",
  "modality": "MULTIMODAL_VISION_VOICE_GIS",
  "severity_score": 92,
  "sla_target": "2 Hours (Emergency)",
  "enforced_sla_hours": 2,
  "resolved_in": "Active countdown",
  "category": "ROADS_AND_PAVEMENTS",
  "primary_department": "Public Works Department (PWD / BBMP Roads)",
  "secondary_department": "Traffic Police Infrastructure Wing",
  "jurisdiction": {
    "city": "Bengaluru (BBMP)",
    "ward_name": "Old Thippasandra",
    "ward_number": "121",
    "executive_engineer": "EE-Ward-121 (Old Thippasandra)",
    "hotline": "+91-80-2222-1188"
  },
  "coordinates": {
    "latitude": 12.9716,
    "longitude": 77.6412
  },
  "spatial_deduplication": {
    "is_duplicate": false,
    "action": "CREATE_NEW_WORK_ORDER",
    "matched_parent_ticket": null,
    "distance_meters": null,
    "total_citizen_reports": 1
  },
  "proof_of_repair": {
    "before_image": "damage_crater_01.jpg",
    "after_image": null,
    "contractor_verified_at": null,
    "citizen_disputed": false,
    "dispute_reason": null
  },
  "tamper_evident_audit_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
```

---

## 🌐 FastAPI Backend Integration Blueprint

For agents developing a centralized microservices backend or REST Gateway, wrap the subsystem as follows:

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
    image: UploadFile = File(None),
    audio: UploadFile = File(None)
):
    # 1. Resolve Location & Deduplication
    ward_info = gis_router.resolve_location(lat, lon)
    dup_info = gis_router.check_spatial_duplicate(lat, lon, "Civic Defect")
    
    # 2. Process Vision (if present)
    vision_res = None
    if image:
        temp_img = f"/tmp/{image.filename}"
        with open(temp_img, "wb") as f:
            shutil.copyfileobj(image.file, f)
        vision_res = vision_engine.analyze_image(temp_img)
        
    # 3. Process Audio (if present)
    audio_res = None
    if audio:
        temp_aud = f"/tmp/{audio.filename}"
        with open(temp_aud, "wb") as f:
            shutil.copyfileobj(audio.file, f)
        audio_res = audio_engine.analyze_audio_report(temp_aud)

    # 4. Synthesize Severity & Dispatch
    severity = max(
        vision_res["severity_score"] if vision_res else 0,
        audio_res["severity_score"] if audio_res else 0,
        40
    )
    
    return {
        "status": "TRIAGED_AND_DISPATCHED",
        "ward": ward_info,
        "deduplication": dup_info,
        "vision": vision_res,
        "audio": audio_res,
        "severity_score": severity
    }
```

---

## 📊 Benchmark Verification

* **Road Pothole Perception**: Tested against 756 real-world benchmark images (Anant Singh Cross Pothole Dataset):
  * Precision: **92.5%**
  * Recall: **90.1%**
  * False Positive Drop: **-52%** (via calibrated internal cutoff $0.38$)
* **Structural Concrete Perception**: Tested against 2,000 concrete fracture images (Surface Crack Benchmark):
  * False Alarms Filtered: **92% reduction** via edge-preserving bilateral filter (`d=5, sigmaColor=30`) and curvilinear thinness constraints (`aspect_ratio > 1.8`, `thinness > 14`).
* **Geospatial Resolution**: Shapely Ray-Casting over 243 ward boundary multipolygons executes in **$< 3\text{ ms}$** on standard single-core CPU.

---

## 💻 Running the Live Demonstration

```bash
# 1. Install Dependencies
pip install -r requirements.txt

# 2. Launch Streamlit Application
streamlit run src/app_demo.py --server.port 8501
```
* **Tab 1**: Unified Ingestion (Photo + Voice + Interactive Drag-and-Drop Map Pin).
* **Tab 2**: Public Accountability Ledger (Before/After Photographic Proof + Citizen Dispute / Re-complaint Mechanism).
