"""
Full Dataset Evaluation — All 712 images (train + test)
Tests pothole_best.pt on every image in the repository.
"""

import os
from ultralytics import YOLO

WEIGHTS  = r"C:\Users\admin\.gemini\antigravity\scratch\civic-triage-system\pothole_best.pt"
ROOT     = r"C:\Users\admin\.gemini\antigravity\scratch\civic-triage-system\anant_dataset\My Dataset"
CONF     = 0.25
EXTS     = (".jpg", ".jpeg", ".png", ".bmp")

model = YOLO(WEIGHTS)

splits = {
    "train/Pothole": ("pothole", os.path.join(ROOT, "train", "Pothole")),
    "train/Plain":   ("plain",   os.path.join(ROOT, "train", "Plain")),
    "test/Pothole":  ("pothole", os.path.join(ROOT, "test",  "Pothole")),
    "test/Plain":    ("plain",   os.path.join(ROOT, "test",  "Plain")),
}

grand = {"TP": 0, "TN": 0, "FP": 0, "FN": 0}
split_results = {}

for split_name, (expected, folder) in splits.items():
    files = [f for f in os.listdir(folder) if f.lower().endswith(EXTS)]
    TP = TN = FP = FN = 0
    print(f"\n[*] Evaluating {split_name} ({len(files)} images)...")

    for fname in files:
        path = os.path.join(folder, fname)
        res  = model(path, conf=CONF, verbose=False)[0]
        detected = len(res.boxes) > 0

        if expected == "pothole":
            if detected: TP += 1
            else:        FN += 1
        else:
            if not detected: TN += 1
            else:            FP += 1

    split_results[split_name] = {"TP": TP, "TN": TN, "FP": FP, "FN": FN, "total": len(files)}
    for k in grand: grand[k] += split_results[split_name][k]
    total = len(files)
    correct = TP + TN
    acc = round(correct / total * 100, 1) if total else 0
    print(f"    TP={TP} TN={TN} FP={FP} FN={FN} | Accuracy: {acc}% ({correct}/{total})")

# Grand summary
TP, TN, FP, FN = grand["TP"], grand["TN"], grand["FP"], grand["FN"]
total = TP + TN + FP + FN
acc   = round((TP + TN) / total * 100, 2)
prec  = round(TP / (TP + FP) * 100, 2) if (TP + FP) else 0
rec   = round(TP / (TP + FN) * 100, 2) if (TP + FN) else 0
f1    = round(2 * prec * rec / (prec + rec), 2) if (prec + rec) else 0
spec  = round(TN / (TN + FP) * 100, 2) if (TN + FP) else 0

print("\n" + "="*62)
print("  GRAND TOTAL EVALUATION — ALL 712 IMAGES")
print("="*62)
print(f"  Split Breakdown:")
for sn, sr in split_results.items():
    tot = sr["total"]
    cor = sr["TP"] + sr["TN"]
    print(f"    {sn:<20}: {cor:>3}/{tot:>3} correct  ({round(cor/tot*100,1)}%)")

print(f"\n  Confusion Matrix (All 712 images):")
print(f"  ┌───────────────────────────────────────────────┐")
print(f"  │  True Positives  (TP): {TP:>4}                     │")
print(f"  │  True Negatives  (TN): {TN:>4}                     │")
print(f"  │  False Positives (FP): {FP:>4}  (clean → flagged)  │")
print(f"  │  False Negatives (FN): {FN:>4}  (pothole → missed) │")
print(f"  └───────────────────────────────────────────────┘")
print(f"\n  ┌───────────────────────────────────────────────┐")
print(f"  │  Overall Accuracy :  {acc:>6}%  ({TP+TN}/{total})        │")
print(f"  │  Precision        :  {prec:>6}%                     │")
print(f"  │  Recall           :  {rec:>6}%                     │")
print(f"  │  F1-Score         :  {f1:>6}%                     │")
print(f"  │  Specificity      :  {spec:>6}%  (clean road accuracy)│")
print(f"  └───────────────────────────────────────────────┘")
print("\n  DONE.")
