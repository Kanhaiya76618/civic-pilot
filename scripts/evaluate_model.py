"""
Civic Triage - Model Evaluation on Anant Singh Cross Dataset
Tests pothole_best.pt on:
  test/Plain/   -> Expected: NO detection (True Negative)
  test/Pothole/ -> Expected: Detection found (True Positive)
"""

import os
import sys
import json
import cv2
import numpy as np
from ultralytics import YOLO

WEIGHTS = r"C:\Users\admin\.gemini\antigravity\scratch\civic-triage-system\pothole_best.pt"
DATASET_ROOT = r"C:\Users\admin\.gemini\antigravity\scratch\civic-triage-system\anant_dataset\My Dataset"
TEST_PLAIN   = os.path.join(DATASET_ROOT, "test", "Plain")
TEST_POTHOLE = os.path.join(DATASET_ROOT, "test", "Pothole")
CONF_THRESHOLD = 0.25

model = YOLO(WEIGHTS)
print(f"[+] Model loaded: pothole_best.pt | Classes: {list(model.names.values())}")

results_log = []

def evaluate_folder(folder, expected_label, label_name):
    exts = (".jpg", ".jpeg", ".png", ".bmp")
    files = [f for f in os.listdir(folder) if f.lower().endswith(exts)]
    TP = TN = FP = FN = 0
    details = []

    for fname in files:
        path = os.path.join(folder, fname)
        res = model(path, conf=CONF_THRESHOLD, verbose=False)[0]
        detected = len(res.boxes) > 0
        max_conf = max((float(b.conf[0]) for b in res.boxes), default=0.0)

        if expected_label == "pothole":
            correct = detected
            outcome = "TP" if detected else "FN"
            if detected: TP += 1
            else:        FN += 1
        else:
            correct = not detected
            outcome = "TN" if not detected else "FP"
            if not detected: TN += 1
            else:            FP += 1

        details.append({
            "file": fname,
            "expected": label_name,
            "detected_pothole": detected,
            "num_boxes": len(res.boxes),
            "max_confidence": round(max_conf, 3),
            "outcome": outcome,
            "correct": correct
        })

    return TP, TN, FP, FN, details

print("\n" + "="*60)
print("  EVALUATING: test/Pothole/ (should all be detected)")
print("="*60)
TP, _, FP, FN, pothole_details = evaluate_folder(TEST_POTHOLE, "pothole", "Pothole")

print("\n" + "="*60)
print("  EVALUATING: test/Plain/ (should have NO detections)")
print("="*60)
_, TN, FP2, _, plain_details = evaluate_folder(TEST_PLAIN, "plain", "Plain Road")

# --- AGGREGATE METRICS ---
FP = FP + FP2
total = TP + TN + FP + FN

accuracy   = round((TP + TN) / total * 100, 2) if total else 0
precision  = round(TP / (TP + FP) * 100, 2) if (TP + FP) else 0
recall     = round(TP / (TP + FN) * 100, 2) if (TP + FN) else 0
f1         = round(2 * precision * recall / (precision + recall), 2) if (precision + recall) else 0
specificity= round(TN / (TN + FP2) * 100, 2) if (TN + FP2) else 0

print("\n" + "="*60)
print("  MODEL EVALUATION REPORT — pothole_best.pt")
print("="*60)
print(f"\n  Dataset:    Anant Singh Cross / CNN Pothole Detection")
print(f"  Total Images Evaluated: {total}")
print(f"  └─ Pothole Images:  {TP + FN}  (expected detection)")
print(f"  └─ Plain Images:    {TN + FP2}  (expected no detection)")
print(f"\n  Confusion Matrix:")
print(f"  ┌─────────────────────────────────────────────┐")
print(f"  │  True Positives  (TP): {TP:>3}  (Pothole ✓ found)  │")
print(f"  │  True Negatives  (TN): {TN:>3}  (Clean road ✓ clear)│")
print(f"  │  False Positives (FP): {FP:>3}  (Clean road ✗ flagged)│")
print(f"  │  False Negatives (FN): {FN:>3}  (Pothole ✗ missed) │")
print(f"  └─────────────────────────────────────────────┘")
print(f"\n  ┌─────────────────────────────────────────────┐")
print(f"  │  Accuracy:    {accuracy:>6}%                      │")
print(f"  │  Precision:   {precision:>6}%                      │")
print(f"  │  Recall:      {recall:>6}%                      │")
print(f"  │  F1-Score:    {f1:>6}%                      │")
print(f"  │  Specificity: {specificity:>6}%  (Clean road rejection) │")
print(f"  └─────────────────────────────────────────────┘")

print("\n  Per-Image Breakdown (Pothole Class):")
print(f"  {'File':<35} {'Boxes':>5} {'MaxConf':>8} {'Outcome':>8}")
print(f"  {'-'*60}")
for d in pothole_details:
    mark = "✓" if d["correct"] else "✗"
    print(f"  {mark} {d['file']:<33} {d['num_boxes']:>5} {d['max_confidence']:>8.3f} {d['outcome']:>8}")

print("\n  Per-Image Breakdown (Plain Road Class):")
print(f"  {'File':<35} {'Boxes':>5} {'MaxConf':>8} {'Outcome':>8}")
print(f"  {'-'*60}")
for d in plain_details:
    mark = "✓" if d["correct"] else "✗"
    print(f"  {mark} {d['file']:<33} {d['num_boxes']:>5} {d['max_confidence']:>8.3f} {d['outcome']:>8}")

print("\n" + "="*60)
print("  EVALUATION COMPLETE")
print("="*60)
