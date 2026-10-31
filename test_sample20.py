import os
import cv2
import sys

sys.path.append(r"C:\Users\admin\.gemini\antigravity\scratch\civic-triage-system\src")
from vision_triage import CivicVisionTriageEngine

engine = CivicVisionTriageEngine()

pos_dir = r"C:\Users\admin\.gemini\antigravity\scratch\civic-triage-system\data\ai_datasets\vision_damage\bridge_crack\Positive"
neg_dir = r"C:\Users\admin\.gemini\antigravity\scratch\civic-triage-system\data\ai_datasets\vision_damage\bridge_crack\Negative"

pos_files = os.listdir(pos_dir)[:20]
neg_files = os.listdir(neg_dir)[:20]

pos_hits = sum(1 for f in pos_files if len(engine.analyze_image(os.path.join(pos_dir, f), "bridge")["detected_defects"]) > 0)
neg_hits = sum(1 for f in neg_files if len(engine.analyze_image(os.path.join(neg_dir, f), "bridge")["detected_defects"]) == 0)

print(f"Positive Detected (TP): {pos_hits}/20 ({pos_hits*5}%)")
print(f"Negative Clean (TN): {neg_hits}/20 ({neg_hits*5}%)")
