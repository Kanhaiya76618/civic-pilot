"""
Swayam-sevak Triage & Perception Engine
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


def lookup_ward(lat: float, lng: float, district: Optional[str] = None) -> Tuple[str, str, str]:
    """Finds ward containing given lat/lng via Point-in-Polygon. Outside the ward maps we have, it says so: the
    report keeps its district (from the PIN code) and is marked unmapped, never given a made-up ward."""
    wards = load_ward_boundaries()
    pt = Point(lng, lat)  # GeoJSON is [lng, lat]
    for w in wards:
        if w["polygon"].contains(pt):
            return w["ward_id"], w["ward_name"], w["city"]
    return "UNMAPPED", "Ward not mapped yet", (district or "Outside mapped cities").strip()[:100]


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
            return str(r.id)  # PostgreSQL hands back a UUID object; payloads and lookups need text
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

def assess_image(image_bytes: bytes, potholes: bool = True) -> Dict[str, Any]:
    """
    potholes=False (any category but roads): only the blur check runs; the pothole model and the crack texture
    measure are about road surfaces and would mislabel garbage or a lamp post.
    Analyzes photo using:
    - Laplacian blur detection
    - Black-hat crack morphology
    - YOLOv8 pothole detection (if weights loaded)
    """
    result = {
        "pothole_detected": False,
        "pothole_confidence": 0.0,
        "pothole_count": 0,
        "largest_pothole_pct": 0.0,  # of the photo's area; the photo has no scale, so no square metres
        "detections": [],  # normalised boxes [x0, y0, x1, y1] with confidence, for drawing
        "method": None,  # "yolo" (the trained pothole model) or "texture" (a fallback guess from crack texture)
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
        result["is_blurry"] = bool(blur_var < 80.0)
        if not potholes:
            return result

        # 2. Black-Hat Crack Morphology
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
        _, thresh = cv2.threshold(blackhat, 40, 255, cv2.THRESH_BINARY)
        crack_ratio = np.sum(thresh == 255) / float(thresh.size)
        result["crack_percentage"] = round(float(crack_ratio * 100), 2)

        # 3. YOLOv8 Pothole Detection
        yolo = get_yolo_model()
        if yolo:
            result["method"] = "yolo"
            yolo_res = yolo.predict(img, conf=0.25, verbose=False)
            if yolo_res and len(yolo_res) > 0 and len(yolo_res[0].boxes) > 0:
                boxes = yolo_res[0].boxes
                found = sorted(((float(c), [round(float(v), 4) for v in xy]) for c, xy in
                                zip(boxes.conf.cpu().numpy(), boxes.xyxyn.cpu().numpy())), reverse=True)
                result["detections"] = [{"box": xy, "confidence": round(c, 3)} for c, xy in found]
                result["pothole_detected"] = True
                result["pothole_count"] = len(found)
                result["pothole_confidence"] = round(found[0][0], 3)
                result["largest_pothole_pct"] = round(max((b[2] - b[0]) * (b[3] - b[1]) for _, b in found) * 100, 1)
        elif result["crack_percentage"] > 3.0:
            # Fallback heuristic if YOLO model not loaded
            result["method"] = "texture"
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
    db = None,
    district: Optional[str] = None,
    perception: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Unified triage pipeline computing ward, deduplication, severity, and SLA.
    """
    # 1. Ward Lookup
    ward_id, ward_name, city = lookup_ward(lat, lng, district)

    # 2. Perception (CV & NLP)
    if perception is None:  # callers that already ran the photo check pass it in, so the model runs once
        perception = assess_image(image_bytes) if image_bytes else {}

    detected_cat, urgency = analyze_text_intent(description)
    final_category = category or detected_cat or "other"

    # 3. Spatial Deduplication (50 meters)
    dup_report_id = None
    if db is not None:
        dup_report_id = find_duplicate_report(db, lat, lng, final_category, radius_m=50.0)

    # 4. Critical POI Multiplier
    nearest_poi, poi_dist, multiplier = get_nearest_poi(lat, lng)

    # 5. Severity Rating Computation
    base_severity, reasons = "P3", []
    seen = perception.get("vision") or {}
    danger = seen.get("problem_visible") and (seen.get("severity") == "high" or seen.get("hazards"))
    if urgency == "critical" or "burst" in description.lower() or "hospital" in description.lower():
        base_severity = "P1"
        reasons.append("The description mentions an emergency or a danger to people.")
    elif danger:
        base_severity = "P2"
        what = "; ".join(seen.get("hazards") or []) or seen.get("issue") or "a serious problem"
        reasons.append(f"The photo shows a danger to people: {what[:1].lower() + what[1:]}.")
    elif perception.get("pothole_detected") and perception.get("pothole_confidence", 0) > 0.6:
        base_severity = "P2"
        reasons.append(f"The photo shows a pothole ({round(perception['pothole_confidence'] * 100)}% confidence).")
    elif perception.get("crack_percentage", 0) > 5.0 and seen.get("matches_category", True):
        base_severity = "P2"
        reasons.append(f"Rough or cracked surface covers about {perception['crack_percentage']}% of the photo.")
    elif final_category in ["water", "drainage"] and "overflow" in description.lower():
        base_severity = "P2"
        reasons.append("Water or drainage is overflowing.")

    # Bump severity if near hospital/school with multiplier >= 1.4
    final_severity = base_severity
    if multiplier >= 1.4:
        if base_severity == "P2":
            final_severity = "P1"
        elif base_severity == "P3":
            final_severity = "P2"
        if final_severity != base_severity:
            reasons.append(f"It is {round(poi_dist)} m from {nearest_poi}, so it is raised one level.")
    if not reasons:
        reasons.append("No sign of immediate danger, so it gets the standard deadline.")

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
        "perception": perception,
        "reasons": reasons,
        "department": department_for(final_category),
    }


# ----------------- ROUTING & PLAIN-LANGUAGE FINDINGS -----------------

# Which municipal department handles each category (the report form's categories, and the older short ids).
DEPARTMENTS = {
    "Road and Bridges": "Roads & Engineering", "roads_potholes": "Roads & Engineering",
    "Water Supply": "Water Supply", "water": "Water Supply",
    "Sanitation and Garbage": "Solid Waste Management", "garbage": "Solid Waste Management",
    "Street Lights": "Electrical (Street Lighting)", "streetlights": "Electrical (Street Lighting)",
    "drainage": "Drainage & Sewerage", "Pollution": "Environment",
}


def department_for(category: Optional[str]) -> str:
    return DEPARTMENTS.get(category or "", "Ward Office")


SEVERITY_NAMES = {"P1": "Critical", "P2": "High", "P3": "Medium", "P4": "Low"}


def findings(perception: Dict[str, Any]) -> List[str]:
    """What the computer-vision check found in the photo, as plain sentences (no guesses beyond the numbers)."""
    if not perception:
        return []
    out = []
    seen = perception.get("vision") or {}
    if seen.get("shows"):
        out.append(seen["shows"])
        out.extend(seen.get("observations") or [])
        out.extend(f"Danger: {h}" for h in seen.get("hazards") or [])
    if perception.get("method") == "yolo":
        n = perception.get("pothole_count", 0)
        if n:
            out.append(f"{n} pothole{'s' if n > 1 else ''} found by our pothole model "
                       f"(highest confidence {round(perception['pothole_confidence'] * 100)}%).")
            out.append(f"The largest covers about {perception['largest_pothole_pct']}% of the photo.")
        else:
            out.append("Our pothole model did not find a pothole in this photo.")
    elif perception.get("method") == "texture":
        out.append(f"Possible pothole, judged from surface texture only ({round(perception['pothole_confidence'] * 100)}%).")
    if perception.get("crack_percentage", 0) >= 1:
        out.append(f"Rough or cracked surface covers about {perception['crack_percentage']}% of the photo.")
    out.append("The photo is blurry: a sharper photo gives a better assessment." if perception.get("is_blurry")
               else "The photo is sharp enough to assess.")
    return out


def annotate(image_bytes: bytes, detections: List[Dict[str, Any]], max_side: int = 1000) -> Optional[bytes]:
    """The photo with each detected pothole outlined and labelled, as JPEG (for the citizen's preview and the desk)."""
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    scale = max_side / max(img.shape[:2])
    if scale < 1:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    h, w = img.shape[:2]
    thick = max(2, round(max(h, w) / 300))
    for i, d in enumerate(detections, 1):
        x0, y0, x1, y1 = (int(v * s) for v, s in zip(d["box"], (w, h, w, h)))
        cv2.rectangle(img, (x0, y0), (x1, y1), (51, 153, 255), thick)  # saffron, BGR
        label = f"Pothole {i}: {round(d['confidence'] * 100)}%"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        ty = max(th + 8, y0)
        cv2.rectangle(img, (x0, ty - th - 8), (x0 + tw + 8, ty), (51, 153, 255), -1)
        cv2.putText(img, label, (x0 + 4, ty - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (64, 33, 19), 2, cv2.LINE_AA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return buf.tobytes() if ok else None
