# 🏛️ Transparent Civic Grievance & Infrastructure Triage System (`2-CV`)

An open-source, AI-driven autonomous triage engine for municipal public works, disaster mitigation, and citizen grievance management.

Combines **Multi-Hazard Computer Vision**, **Offline Speech Recognition (Whisper)**, and **Vector GIS Ward Boundary Resolution** into a unified public accountability ledger.

---

## 🚀 Key Modules

### 1. Multi-Hazard Vision Triage (`src/vision_triage.py`)
* **Gate-1 Anti-Spam & OOD Filter**: Uses ImageNet classification to instantly discard non-civic photos (food, pets, memes) with a 0/100 severity before wasting municipal field resources.
* **Road Defect Detection**: Fine-tuned YOLOv8 model calibrated to **91.53% accuracy** and **92.5% precision**, slashing false alarms by over 52%.
* **Bridge & Concrete Structural Fracture**: Adaptive black top-hat morphology + edge-preserving bilateral filtering + curvilinear thinness hysteresis to detect concrete fissure propagation and trigger 2-hour emergency life-safety SLAs.

### 2. Autonomous Audio & Voice Note Triage (`src/audio_triage.py`)
* **Universal Audio Ingestion**: Uses PyAV to decode MP3, WAV, AAC, and M4A directly into memory without requiring external FFmpeg binaries.
* **Offline Speech-to-Text**: Powered by `openai/whisper-tiny` running on PyTorch CPU.
* **Distress & Intent Classifier**: Detects critical emergency keywords (*"accident"*, *"school"*, *"collapsed"*, *"burst pipe"*), extracts location landmarks (*"100 Feet Road"*, *"Pillar 14"*), and assigns lead municipal agencies automatically.

### 3. Geospatial Ward Routing & Spatial Deduplication (`src/gis_routing.py`)
* **Point-in-Polygon Ward Resolution**: Vector geometric indexing against **243 Bangalore BBMP Wards** and Pune PMC wards using Shapely. Identifies the exact Ward Name, Ward Number, and Zonal Executive Engineer in ~2 ms.
* **50-Meter Proximity Deduplication**: Auto-merges duplicate citizen reports submitted within 50 meters into a single work order, preventing double contractor billing while elevating community urgency votes.
* **POI Vulnerability Multiplier**: Automatically accelerates repair SLAs if defects are within 500 meters of a hospital, trauma center, or school.

### 4. Interactive Multimodal Web App (`src/app_demo.py`)
* **Unified Ingestion**: Submit Photo Evidence, Voice Note, or both simultaneously.
* **True Drag-and-Drop Pin Map**: Grab and drag the incident pin along the street with real-time ward recalculation.
* **Public Transparency Ledger**: Live status tracking with **Before vs. After Repair Photos** and a **Citizen Dispute / Re-Complaint** mechanism against substandard contractor patches.

---

## 🛠️ Quickstart

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Launch the Application
```bash
streamlit run src/app_demo.py --server.port 8501
```
Open `http://localhost:8501` in your browser.

---

## 📂 Repository Structure
```
├── src/
│   ├── app_demo.py                  # Main Streamlit Web Application
│   ├── vision_triage.py             # Gate 1 (Spam) & Gate 2 (YOLO + Fissure CV)
│   ├── audio_triage.py              # Whisper ASR & Distress Intent Engine
│   ├── gis_routing.py               # Point-in-Polygon & 50m Deduplication
│   └── static/draggable_pin_map/    # Interactive Drag-and-Drop Leaflet Map
├── data/
│   ├── gis/ward_boundaries/         # Official BBMP (243 wards) & PMC GeoJSON
│   ├── gis/pois/                    # Critical POIs (Hospitals, Metro, Schools)
│   ├── ai_datasets/audio_samples/   # Preloaded civic voice grievance calls
│   └── grievance_ledger.json        # Persistent public accountability database
├── backups/                         # Verified baseline versions
├── pothole_best.pt                  # Fine-tuned YOLOv8 weights (22.5 MB)
├── requirements.txt
└── README.md
```
