"""
CivicPilot Triage & Perception Engine
Integrates:
1. Multimodal perception (YOLOv8 pothole detection, black-hat crack morphology, Laplacian blur filter)
2. Civic speech/text intent classifier
3. GIS ward Point-In-Polygon (PIP) mapping (Bangalore BBMP, Pune PMC, Delhi)
4. Spatial 50-meter deduplication and merge-and-upvote logic
5. Critical infrastructure POI proximity multiplier (1.2 - 1.6x)
"""

import os
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple, List
import numpy as np
import cv2
from shapely.geometry import Point, shape

# Try importing ultralytics for YOLOv8 pothole weights
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "gis")
POI_PATH = os.path.join(DATA_DIR, "pois", "critical_infrastructure_pois.json")
POTHOLE_WEIGHTS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pothole_best.pt")

_yolo_model = None
def get_yolo_model():
    global _yolo_model
    if _yolo_model is None and YOLO_AVAILABLE and os.path.exists(POTHOLE_WEIGHTS_PATH):
        try:
            _yolo_model = YOLO(POTHOLE_WEIGHTS_PATH)
        except Exception as e:
            print("Failed to initialize YOLO model:", e)
            _yolo_model = False
    return _yolo_model if _yolo_model is not False else None


# ----------------- GIS & WARD LOOKUP -----------------

_ward_cache = []

def load_ward_boundaries():
    global _ward_cache
    if _ward_cache:
        return _ward_cache

    wards_dir = os.path.join(DATA_DIR, "ward_boundaries")
    if not os.path.exists(wards_dir):
        return []

    for fname in os.listdir(wards_dir):
        if not fname.endswith(".geojson"):
            continue
        path = os.path.join(wards_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            features = data.get("features", [])
            for feat in features:
                geom = shape(feat.get("geometry"))
                props = feat.get("properties", {})
                # Extract ward identifiers across different city datasets
                ward_id = str(props.get("KGISWardNo") or props.get("WARD_NO") or props.get("ward_no") or props.get("Ward_No") or props.get("id") or props.get("FID") or "UNKNOWN")
                ward_name = str(props.get("KGISWardName") or props.get("WARD_NAME") or props.get("ward_name") or props.get("Ward_Name") or props.get("NAME") or props.get("name") or f"Ward {ward_id}")
                city = "Bengaluru" if "bangalore" in fname else ("Pune" if "pune" in fname else ("Delhi" if "delhi" in fname else "India"))
                _ward_cache.append({
                    "polygon": geom,
                    "ward_id": f"{'BBMP' if city == 'Bengaluru' else ('PMC' if city == 'Pune' else 'MCD')}-{ward_id}",
                    "ward_name": ward_name,
                    "city": city
                })
        except Exception as e:
            print(f"Error loading {fname}:", e)
    return _ward_cache


def lookup_ward(lat: float, lng: float) -> Tuple[str, str, str]:
    """Finds ward containing given lat/lng via Point-in-Polygon."""
    wards = load_ward_boundaries()
    pt = Point(lng, lat)  # GeoJSON is [lng, lat]
    for w in wards:
        if w["polygon"].contains(pt):
            return w["ward_id"], w["ward_name"], w["city"]

    # Fallback to nearest city center if outside explicit boundaries
    if 12.8 <= lat <= 13.2 and 77.4 <= lng <= 77.8:
        return "BBMP-111", "Shantinagar", "Bengaluru"
    elif 18.4 <= lat <= 18.7 and 73.7 <= lng <= 74.0:
        return "PMC-12", "Kothrud", "Pune"
    elif 28.4 <= lat <= 28.9 and 77.0 <= lng <= 77.4:
        return "MCD-54", "Karol Bagh", "Delhi"
    return "WARD-01", "Central Ward", "Urban Local Body"


# ----------------- HAVERSINE & SPATIAL DEDUP -----------------

def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two GPS coordinates in meters."""
    R = 6371000.0  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def find_duplicate_report(db, lat: float, lng: float, category: str, radius_m: float = 50.0) -> Optional[str]:
    """Checks for active reports in same category within radius_m meters."""
    from server.db import Report
    # Query reports in non-terminal states
    active_reports = db.query(Report).filter(
        Report.category == category,
        Report.status.in_(["SUBMITTED", "TRIAGED", "ACKNOWLEDGED", "ASSIGNED", "IN_PROGRESS"]),
        Report.duplicate_of.is_(None)
    ).all()

    for r in active_reports:
        dist = haversine_distance_m(lat, lng, r.latitude, r.longitude)
        if dist <= radius_m:
            return r.id
    return None


# ----------------- POI PROXIMITY & MULTIPLIER -----------------

_pois_cache = []

def load_pois():
    global _pois_cache
    if _pois_cache:
        return _pois_cache
    if os.path.exists(POI_PATH):
        try:
            with open(POI_PATH, "r", encoding="utf-8") as f:
                _pois_cache = json.load(f)
        except Exception:
            _pois_cache = []
    return _pois_cache


def get_nearest_poi(lat: float, lng: float) -> Tuple[Optional[str], Optional[float], float]:
    """
    Returns (nearest_poi_name, distance_m, multiplier).
    Hospitals/schools/bridges within 100m apply 1.2x - 1.6x priority multiplier.
    """
    pois = load_pois()
    if not pois:
        return None, None, 1.0

    nearest_name = None
    min_dist = float("inf")
    poi_weight = 1.0

    for poi in pois:
        d = haversine_distance_m(lat, lng, poi.get("lat", 0.0), poi.get("lng", 0.0))
        if d < min_dist:
            min_dist = d
            nearest_name = poi.get("name", "Critical Infrastructure")
            poi_weight = poi.get("priority_weight", 1.5)

    if min_dist <= 150.0:
        multiplier = round(min(1.6, 1.0 + (poi_weight - 1.0) * (1.0 - min_dist / 150.0)), 2)
        return nearest_name, round(min_dist, 1), multiplier

    return None, round(min_dist, 1), 1.0


# ----------------- COMPUTER VISION TRIAGE -----------------

def assess_image(image_bytes: bytes) -> Dict[str, Any]:
    """
    Analyzes photo using:
    - Laplacian blur detection
    - Black-hat crack morphology
    - YOLOv8 pothole detection (if weights loaded)
    """
    result = {
        "pothole_detected": False,
        "pothole_confidence": 0.0,
        "crack_percentage": 0.0,
        "blur_score": 0.0,
        "is_blurry": False
    }

    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return result

        # 1. Blur Detection (Laplacian variance)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        result["blur_score"] = round(float(blur_var), 2)
        result["is_blurry"] = blur_var < 80.0

        # 2. Black-Hat Crack Morphology
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
        _, thresh = cv2.threshold(blackhat, 40, 255, cv2.THRESH_BINARY)
        crack_ratio = np.sum(thresh == 255) / float(thresh.size)
        result["crack_percentage"] = round(float(crack_ratio * 100), 2)

        # 3. YOLOv8 Pothole Detection
        yolo = get_yolo_model()
        if yolo:
            yolo_res = yolo.predict(img, conf=0.25, verbose=False)
            if yolo_res and len(yolo_res) > 0 and len(yolo_res[0].boxes) > 0:
                top_conf = float(yolo_res[0].boxes.conf.max().cpu().numpy())
                result["pothole_detected"] = True
                result["pothole_confidence"] = round(top_conf, 3)
        elif result["crack_percentage"] > 3.0:
            # Fallback heuristic if YOLO model not loaded
            result["pothole_detected"] = True
            result["pothole_confidence"] = min(0.95, round(result["crack_percentage"] / 10.0, 2))

    except Exception as e:
        print("Error assessing image:", e)

    return result


# ----------------- INTENT & SEVERITY TRIAGE -----------------

CIVIC_LEXICON = {
    "roads_potholes": ["pothole", "crater", "road", "asphalt", "khadda", "gaddha", "accident", "skid", "broken road"],
    "water": ["water", "leak", "pipe", "burst", "supply", "paani", "drinking water", "contamination", "pipeline"],
    "garbage": ["garbage", "trash", "waste", "dump", "kachra", "debris", "rubble", "overflowing", "smell", "filth"],
    "streetlights": ["light", "dark", "lamp", "pole", "wire", "bijli", "andhera", "broken light", "sodium lamp"],
    "drainage": ["drain", "drainage", "manhole", "sewage", "stormwater", "nalah", "blocked drain", "overflow"]
}

def analyze_text_intent(text: str) -> Tuple[Optional[str], str]:
    """Extracts category and urgency hints from text or transcription."""
    text_lower = text.lower()
    detected_cat = None
    urgency = "normal"

    urgent_keywords = ["danger", "emergency", "hospital", "urgent", "critical", "burst", "hazard", "death", "severe"]
    if any(k in text_lower for k in urgent_keywords):
        urgency = "critical"

    for cat, kws in CIVIC_LEXICON.items():
        if any(k in text_lower for k in kws):
            detected_cat = cat
            break

    return detected_cat, urgency


def compute_triage_decision(
    category: str,
    description: str,
    lat: float,
    lng: float,
    image_bytes: Optional[bytes] = None,
    db = None
) -> Dict[str, Any]:
    """
    Unified triage pipeline computing ward, deduplication, severity, and SLA.
    """
    # 1. Ward Lookup
    ward_id, ward_name, city = lookup_ward(lat, lng)

    # 2. Perception (CV & NLP)
    perception = {}
    if image_bytes:
        perception = assess_image(image_bytes)

    detected_cat, urgency = analyze_text_intent(description)
    final_category = category or detected_cat or "other"

    # 3. Spatial Deduplication (50 meters)
    dup_report_id = None
    if db is not None:
        dup_report_id = find_duplicate_report(db, lat, lng, final_category, radius_m=50.0)

    # 4. Critical POI Multiplier
    nearest_poi, poi_dist, multiplier = get_nearest_poi(lat, lng)

    # 5. Severity Rating Computation
    base_severity = "P3"
    if urgency == "critical" or "burst" in description.lower() or "hospital" in description.lower():
        base_severity = "P1"
    elif perception.get("pothole_detected") and perception.get("pothole_confidence", 0) > 0.6:
        base_severity = "P2"
    elif perception.get("crack_percentage", 0) > 5.0:
        base_severity = "P2"
    elif final_category in ["water", "drainage"] and "overflow" in description.lower():
        base_severity = "P2"

    # Bump severity if near hospital/school with multiplier >= 1.4
    final_severity = base_severity
    if multiplier >= 1.4:
        if base_severity == "P2":
            final_severity = "P1"
        elif base_severity == "P3":
            final_severity = "P2"

    # SLA deadlines: P1 = 24h, P2 = 48h, P3 = 72h, P4 = 120h
    sla_map = {"P1": 24, "P2": 48, "P3": 72, "P4": 120}
    sla_hours = sla_map.get(final_severity, 72)

    return {
        "assigned_ward_id": ward_id,
        "assigned_ward_name": ward_name,
        "city": city,
        "category": final_category,
        "severity": final_severity,
        "sla_hours": sla_hours,
        "sla_deadline": (datetime.now(timezone.utc) + timedelta(hours=sla_hours)),
        "poi_multiplier": multiplier,
        "nearest_poi": nearest_poi,
        "nearest_poi_distance_m": poi_dist,
        "duplicate_of": dup_report_id,
        "perception": perception
    }
