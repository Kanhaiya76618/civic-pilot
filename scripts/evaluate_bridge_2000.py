"""
Civic Grievance & Infrastructure Triage System
Bridge Structural Crack Evaluation Suite
Evaluates our model on 1,000 Positive (cracked) and 1,000 Negative (clean) images.
Total: 2,000 images.
"""

import os
import sys
import time
import random

sys.path.append(r"C:\Users\admin\.gemini\antigravity\scratch\civic-triage-system\src")
from vision_triage import CivicVisionTriageEngine

DATA_ROOT = r"C:\Users\admin\.gemini\antigravity\scratch\civic-triage-system\data\ai_datasets\vision_damage\bridge_crack"
POS_DIR   = os.path.join(DATA_ROOT, "Positive")
NEG_DIR   = os.path.join(DATA_ROOT, "Negative")

NUM_SAMPLES_EACH = 1000

print("=" * 65)
print("  BRIDGE CRACK EVALUATION - 2,000 IMAGE BENCHMARK")
print("=" * 65)

# Initialize engine
engine = CivicVisionTriageEngine()

# Gather files
random.seed(42)
all_pos = sorted(os.listdir(POS_DIR))
all_neg = sorted(os.listdir(NEG_DIR))

selected_pos = random.sample(all_pos, NUM_SAMPLES_EACH)
selected_neg = random.sample(all_neg, NUM_SAMPLES_EACH)

print(f"[+] Loaded {len(selected_pos)} Positive (Crack) images")
print(f"[+] Loaded {len(selected_neg)} Negative (Clean) images")
print("[*] Running inference on 2,000 images...\n")

TP = 0  # Real crack -> detected
FN = 0  # Real crack -> missed
TN = 0  # Clean surface -> no defect
FP = 0  # Clean surface -> false alarm

start_time = time.time()

# 1. Evaluate 1,000 Positive images
print("--- [1/2] Evaluating 1,000 Positive (Crack) Images ---")
for i, fname in enumerate(selected_pos):
    img_path = os.path.join(POS_DIR, fname)
    res = engine.analyze_image(img_path, category_hint="bridge")
    has_defect = len(res["detected_defects"]) > 0
    if has_defect:
        TP += 1
    else:
        FN += 1
    if (i + 1) % 250 == 0:
        print(f"    Progress: {i + 1}/1000 | Detected: {TP} | Missed: {FN}")

# 2. Evaluate 1,000 Negative images
print("\n--- [2/2] Evaluating 1,000 Negative (Clean) Images ---")
for i, fname in enumerate(selected_neg):
    img_path = os.path.join(NEG_DIR, fname)
    res = engine.analyze_image(img_path, category_hint="bridge")
    has_defect = len(res["detected_defects"]) > 0
    if not has_defect:
        TN += 1
    else:
        FP += 1
    if (i + 1) % 250 == 0:
        print(f"    Progress: {i + 1}/1000 | Clean: {TN} | False Alarms: {FP}")

elapsed = time.time() - start_time
total = TP + TN + FP + FN

# Metrics
accuracy   = round((TP + TN) / total * 100, 2)
precision  = round(TP / (TP + FP) * 100, 2) if (TP + FP) else 0
recall     = round(TP / (TP + FN) * 100, 2) if (TP + FN) else 0
f1_score   = round(2 * precision * recall / (precision + recall), 2) if (precision + recall) else 0
specificity= round(TN / (TN + FP) * 100, 2) if (TN + FP) else 0
fps        = round(total / elapsed, 1)

print("\n" + "=" * 65)
print("  FINAL ACCURACY REPORT — BRIDGE CRACK DEFECT MODEL")
print("=" * 65)
print(f"  Dataset:         Surface Crack Detection Benchmark (227x227)")
print(f"  Total Evaluated: {total:,} images (1,000 Positive + 1,000 Negative)")
print(f"  Total Time:      {elapsed:.1f}s ({fps} images/sec)\n")

print("  CONFUSION MATRIX:")
print("  ┌──────────────────────────────────────────────────┐")
print(f"  │  True Positives  (TP):  {TP:>4}  (Cracks detected ✓)     │")
print(f"  │  True Negatives  (TN):  {TN:>4}  (Clean surfaces ✓)     │")
print(f"  │  False Positives (FP):  {FP:>4}  (Clean → false alarm)  │")
print(f"  │  False Negatives (FN):  {FN:>4}  (Cracks missed ✗)      │")
print("  └──────────────────────────────────────────────────┘\n")

print("  PERFORMANCE METRICS:")
print("  ┌──────────────────────────────────────────────────┐")
print(f"  │  Overall Accuracy:   {accuracy:>6}%                       │")
print(f"  │  Recall (Detection): {recall:>6}%  (Found {TP}/1000 cracks)  │")
print(f"  │  Precision:          {precision:>6}%                       │")
print(f"  │  Specificity:        {specificity:>6}%  (Clean rejection)   │")
print(f"  │  F1-Score:           {f1_score:>6}%                       │")
print("  └──────────────────────────────────────────────────┘")
print("=" * 65)
