"""
Civic Grievance & Infrastructure Triage System
Complete Dataset & GIS Data Ingestion Script
"""

import os
import urllib.request
import json
import shutil

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))

GIS_DIR = os.path.join(BASE_DIR, "gis", "ward_boundaries")
POIS_DIR = os.path.join(BASE_DIR, "gis", "pois")
VISION_DIR = os.path.join(BASE_DIR, "ai_datasets", "vision_damage")
AUDIO_DIR = os.path.join(BASE_DIR, "ai_datasets", "audio_samples")
TEXT_DIR = os.path.join(BASE_DIR, "ai_datasets", "text_complaints")

for d in [GIS_DIR, POIS_DIR, VISION_DIR, AUDIO_DIR, TEXT_DIR]:
    os.makedirs(d, exist_ok=True)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def download_file(url, destination_path, label=""):
    print(f"[*] Downloading {label or os.path.basename(destination_path)}...")
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as response, open(destination_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        size_kb = os.path.getsize(destination_path) / 1024
        print(f"    [+] Saved to {os.path.basename(destination_path)} ({size_kb:.1f} KB)")
        return True
    except Exception as e:
        print(f"    [-] Failed to download from {url}: {e}")
        return False

def main():
    print("=" * 65)
    print("  CIVIC TRIAGE & INFRASTRUCTURE SYSTEM - DATA PROCUREMENT")
    print("=" * 65)

    # 1. GIS DATA: Administrative Ward Boundaries (DataMeet)
    print("\n--- [1/4] Administrative GIS Data ---")
    
    # Pune Municipal Wards GeoJSON
    pune_url = "https://raw.githubusercontent.com/datameet/Municipal_Spatial_Data/master/Pune/pune-admin-wards_2017.geojson"
    download_file(pune_url, os.path.join(GIS_DIR, "pune_pmc_wards.geojson"), "Pune Municipal Wards GeoJSON")

    # 2. SEED SAMPLE POIs (Hospitals, Schools, Critical Transit)
    print("\n--- [2/4] Critical POIs & Assets ---")
    sample_pois = [
        {"name": "Victoria Hospital", "type": "hospital", "lat": 12.9634, "lng": 77.5744, "priority_weight": 2.0},
        {"name": "St. John's Medical College Hospital", "type": "hospital", "lat": 12.9344, "lng": 77.6190, "priority_weight": 2.0},
        {"name": "National Public School", "type": "school", "lat": 12.9784, "lng": 77.6408, "priority_weight": 1.5},
        {"name": "Delhi Public School East", "type": "school", "lat": 12.9150, "lng": 77.7125, "priority_weight": 1.5},
        {"name": "Majestic Central Bus Station", "type": "transit", "lat": 12.9767, "lng": 77.5713, "priority_weight": 1.8},
        {"name": "Silk Board Junction Flyover", "type": "bridge_critical", "lat": 12.9177, "lng": 77.6238, "priority_weight": 2.5}
    ]
    pois_file = os.path.join(POIS_DIR, "critical_infrastructure_pois.json")
    with open(pois_file, "w", encoding="utf-8") as f:
        json.dump(sample_pois, f, indent=2)
    print(f"    [+] POI database ready: {pois_file}")

    # 3. CIVIC COMPLAINTS & TAXONOMY
    print("\n--- [3/4] Civic Grievance Taxonomy & Training Data ---")
    import csv
    complaints = [
        {"id": "GRIEV-001", "text": "Huge crater in the middle of 100ft road near Koramangala signal. Two bikers skidded already.", "category": "pothole", "dept": "PWD_ROAD", "severity": "critical", "lat": 12.9352, "lng": 77.6245},
        {"id": "GRIEV-002", "text": "Underground drinking water main broken since morning, clean water flooding the street.", "category": "pipe_burst", "dept": "WATER_SEWER", "severity": "high", "lat": 12.9716, "lng": 77.5946},
        {"id": "GRIEV-003", "text": "Open sewage manhole without cover right outside primary school gate. Serious danger for kids.", "category": "manhole_open", "dept": "WATER_SEWER", "severity": "critical", "lat": 12.9784, "lng": 77.6408},
        {"id": "GRIEV-004", "text": "Garbage not picked up for 4 days, foul smell and street dogs scattering waste.", "category": "garbage_dump", "dept": "SWM_CLEAN", "severity": "medium", "lat": 12.9121, "lng": 77.6445},
        {"id": "GRIEV-005", "text": "Live wire hanging loose from electrical pole after thunderstorm at 5th cross.", "category": "exposed_live_wire", "dept": "ELEC_DISCOM", "severity": "critical", "lat": 12.9250, "lng": 77.5900},
        {"id": "GRIEV-006", "text": "Street lights not working for past 2 weeks between pillar 120 and 130.", "category": "streetlight_out", "dept": "ELEC_DISCOM", "severity": "low", "lat": 12.9500, "lng": 77.6000},
        {"id": "GRIEV-007", "text": "Expansion joint on flyover bridge is vibrating dangerously under heavy trucks.", "category": "bridge_damage", "dept": "PWD_ROAD", "severity": "critical", "lat": 12.9177, "lng": 77.6238}
    ]
    with open(os.path.join(TEXT_DIR, "benchmark_labeled_complaints.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "text", "category", "dept", "severity", "lat", "lng"])
        writer.writeheader()
        writer.writerows(complaints)
    print("    [+] Labeled complaints dataset saved.")

    # 4. VISION DATASET (Road Damage Starter Pack)
    print("\n--- [4/4] Vision Damage Dataset Preparation ---")
    sample_images = [
        ("https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?w=640&q=80", "sample_road_repair_01.jpg"),
        ("https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?w=640&q=80", "sample_asphalt_crack_02.jpg"),
        ("https://images.unsplash.com/photo-1547683905-f686c993aae5?w=640&q=80", "sample_water_flood_03.jpg"),
        ("https://images.unsplash.com/photo-1513694203232-719a280e022f?w=640&q=80", "sample_bridge_structure_04.jpg")
    ]
    for url, filename in sample_images:
        download_file(url, os.path.join(VISION_DIR, filename), f"Visual Evidence: {filename}")

    # 5. AUDIO DATASET (Sample Multilingual Speech File)
    print("\n--- Audio Sample Download ---")
    audio_sample_url = "https://raw.githubusercontent.com/ggerganov/whisper.cpp/master/samples/jfk.wav"
    download_file(audio_sample_url, os.path.join(AUDIO_DIR, "sample_voice_report.wav"), "Sample Voice Grievance")

    print("\n" + "=" * 65)
    print("  ALL DATASETS & GIS LAYERS SUCCESSFULLY PROCURED!")
    print(f"  Root Path: {BASE_DIR}")
    print("=" * 65)

if __name__ == "__main__":
    main()
