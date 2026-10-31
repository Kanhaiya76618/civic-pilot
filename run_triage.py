"""
Civic Vision Triage - CLI Runner & Terminal Visualizer
"""

import os
import sys
import json
from src.vision_triage import CivicVisionTriageEngine

def print_banner(text):
    print("\n" + "=" * 65)
    print(f"  {text}")
    print("=" * 65)

def main():
    print_banner("CIVIC INFRASTRUCTURE VISION TRIAGE - LIVE RUNNER")
    
    engine = CivicVisionTriageEngine("yolov8n.pt")
    data_dir = os.path.join(os.path.dirname(__file__), "data", "ai_datasets", "vision_damage")
    
    test_cases = [
        ("sample_road_repair_01.jpg", "road", "Pothole & Asphalt Depression"),
        ("sample_water_flood_03.jpg", "water", "Water Main Break & Street Flood"),
        ("sample_bridge_structure_04.jpg", "bridge", "Bridge Structural Distress")
    ]
    
    for filename, category, description in test_cases:
        filepath = os.path.join(data_dir, filename)
        if not os.path.exists(filepath):
            continue
            
        print(f"\n[▶] Processing: {description}")
        print(f"    File: {filename} | Category: {category}")
        
        result = engine.analyze_image(filepath, category_hint=category)
        
        # Color coding simulation
        badge = result["severity_level"]
        score = result["severity_score"]
        sla = result["recommended_sla_hours"]
        area = result["damage_surface_coverage_pct"]
        defects = result["defect_count"]
        
        print("\n    ┌────────────────── TRIAGE ASSESSMENT CARD ──────────────────┐")
        print(f"    │ Status:               DISPATCHED TO {category.upper()} DEPT            │")
        print(f"    │ Severity Level:       {badge:<10} (Score: {score}/100)           │")
        print(f"    │ Surface Damage Area:  {area}% of road/asset view              │")
        print(f"    │ Defect Count:         {defects} distinct hazard zones            │")
        print(f"    │ SLA Target Deadline:  Within {sla} Hours                       │")
        print(f"    │ Public HUD Output:    {os.path.basename(result['annotated_image_path']):<35} │")
        print("    └─────────────────────────────────────────────────────────────┘")

    print_banner("ALL TEST RUNS EXECUTED SUCCESSFULLY")

if __name__ == "__main__":
    main()
