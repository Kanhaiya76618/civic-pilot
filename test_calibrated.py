import os
import cv2
import numpy as np

pos_dir = r"C:\Users\admin\.gemini\antigravity\scratch\civic-triage-system\data\ai_datasets\vision_damage\bridge_crack\Positive"
neg_dir = r"C:\Users\admin\.gemini\antigravity\scratch\civic-triage-system\data\ai_datasets\vision_damage\bridge_crack\Negative"

pos_files = os.listdir(pos_dir)[:50]
neg_files = os.listdir(neg_dir)[:50]

def is_crack(img_path):
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    h, w = img.shape
    # Dynamic kernel based on image dimension
    k_size = max(5, int(min(h, w) * 0.035))
    if k_size % 2 == 0: k_size += 1
    
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_size, k_size))
    tophat = cv2.morphologyEx(img, cv2.MORPH_BLACKHAT, kernel)
    
    # Adaptive threshold
    _, thresh = cv2.threshold(tophat, 19, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    min_length = max(30, int(min(h, w) * 0.15))
    
    for cnt in contours:
        length = cv2.arcLength(cnt, False)
        if length > min_length:
            x, y, bw, bh = cv2.boundingRect(cnt)
            major = max(bw, bh)
            minor = min(bw, bh) + 1e-4
            aspect_ratio = major / minor
            area = cv2.contourArea(cnt)
            thinness = (length * length) / (area + 1e-4)
            
            if aspect_ratio > 1.8 and thinness > 14:
                return True
    return False

pos_hits = sum(1 for f in pos_files if is_crack(os.path.join(pos_dir, f)))
neg_hits = sum(1 for f in neg_files if not is_crack(os.path.join(neg_dir, f)))

print(f"Tested 50 Pos / 50 Neg:")
print(f"  Positive Detected (Recall): {pos_hits}/50 ({pos_hits*2}%)")
print(f"  Negative Clean (Specificity): {neg_hits}/50 ({neg_hits*2}%)")
print(f"  Overall Accuracy: {(pos_hits+neg_hits)/100*100}%")
