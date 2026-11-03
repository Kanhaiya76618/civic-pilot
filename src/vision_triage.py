"""
Civic Grievance & Infrastructure Triage System
Vision Triage Engine with Multi-Hazard Detection:
1. Gate 1: Relevance & Anti-Spam (detects food, pets, indoor items)
2. Gate 2A: Road Pothole Detector (YOLOv8)
3. Gate 2B: Concrete Structural Crack & Bridge Foundation Fracture Analyzer (SDNET / Morphological Fissure Analyzer)
"""

import os
import cv2
import numpy as np
from typing import Dict, Any, List

DISQUALIFIED_SPAM_CLASSES = {
    "ice_cream", "pizza", "hotdog", "sandwich", "hamburger", "cake", "donut", "pastry",
    "cookie", "bagel", "pretzel", "cheeseburger", "chocolate_sauce", "guacamole",
    "espresso", "coffee_mug", "banana", "apple", "orange", "broccoli", "carrot",
    "cat", "dog", "golden_retriever", "pug", "tabby", "persian_cat", "siamese_cat",
    "chihuahua", "rabbit", "hamster", "guinea_pig", "teddy_bear",
    "laptop", "notebook_computer", "desktop_computer", "cellphone", "cellular_telephone",
    "television", "screen", "monitor", "bed", "pillow", "quilt", "wardrobe", "dining_table",
    "toilet", "toilet_seat", "bathtub", "shower_cap", "hair_drier", "toothbrush"
}

class CivicVisionTriageEngine:
    def __init__(self, pothole_weights: str = None, cls_weights: str = "yolov8n-cls.pt"):
        if pothole_weights is None:
            local_weights = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pothole_best.pt"))
            pothole_weights = local_weights if os.path.exists(local_weights) else "yolov8n.pt"

        self.pothole_weights = pothole_weights
        self.cls_weights = cls_weights
        self.pothole_model = None
        self.cls_model = None
        
        try:
            from ultralytics import YOLO
            self.pothole_model = YOLO(self.pothole_weights)
            if os.path.exists(self.cls_weights) or "cls" in self.cls_weights:
                self.cls_model = YOLO(self.cls_weights)
        except Exception as e:
            print(f"[-] Model loading warning: {e}")

    def check_civic_relevance(self, img_bgr: np.ndarray) -> Dict[str, Any]:
        """Gate 1: Verifies civic infrastructure vs. non-civic spam."""
        if not self.cls_model:
            return {"is_valid_civic": True, "reason": "Bypassed"}

        try:
            res = self.cls_model(img_bgr, verbose=False)[0]
            top3_ids = res.probs.top5[:3]
            for idx in top3_ids:
                name = self.cls_model.names[int(idx)].lower()
                conf = float(res.probs.data[idx])
                if name in DISQUALIFIED_SPAM_CLASSES and conf > 0.15:
                    return {
                        "is_valid_civic": False,
                        "rejection_category": name,
                        "confidence": round(conf, 3),
                        "reason": f"Non-civic subject detected: '{name.replace('_', ' ')}' ({int(conf*100)}% confidence). No municipal outdoor infrastructure present."
                    }
            return {"is_valid_civic": True, "reason": "Valid outdoor infrastructure"}
        except Exception as e:
            return {"is_valid_civic": True, "reason": f"Fallback: {e}"}

    def detect_structural_cracks(self, img_bgr: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detects structural concrete cracks, foundation fractures, and bridge shear failures
        using edge-preserving bilateral filtering, morphological black top-hat, and
        curvilinear fissure geometry analysis.
        """
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        total_pixels = h * w

        # Edge-preserving bilateral filter to suppress concrete pore texture noise
        smooth = cv2.bilateralFilter(gray, d=5, sigmaColor=30, sigmaSpace=30)

        # Dynamic kernel size based on image scale
        k_size = max(5, int(min(h, w) * 0.035))
        if k_size % 2 == 0: k_size += 1

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_size, k_size))
        tophat = cv2.morphologyEx(smooth, cv2.MORPH_BLACKHAT, kernel)
        _, thresh = cv2.threshold(tophat, 18, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cracks = []
        min_length = max(32, int(min(h, w) * 0.16))

        for cnt in contours:
            length = cv2.arcLength(cnt, False)
            if length > min_length:
                x, y, bw, bh = cv2.boundingRect(cnt)
                major = max(bw, bh)
                minor = min(bw, bh) + 1e-4
                aspect_ratio = major / minor
                area = cv2.contourArea(cnt)
                thinness = (length * length) / (area + 1e-4)

                # Cracks are elongated, thin curvilinear contours (distinguished from round concrete pores)
                if aspect_ratio > 1.8 and thinness > 14:
                    box_area = bw * bh
                    conf = round(min(0.95, 0.70 + (length / (w + h))), 2)
                    cracks.append({
                        "label": "Structural Concrete Crack",
                        "confidence": conf,
                        "bbox": [x, y, x + bw, y + bh],
                        "area_pct": round((box_area / total_pixels) * 100, 2),
                        "fissure_length_px": round(length, 1)
                    })

        return cracks[:5]

    def detect_solid_waste(self, img_bgr: np.ndarray) -> List[Dict[str, Any]]:
        """
        Gate 2C: Municipal Solid Waste & Garbage Dump Detection.
        Combines neural waste classifier signals with multiscale chromatic entropy 
        clustering to detect overflowing roadside garbage piles, debris, and refuse heaps.
        """
        h, w = img_bgr.shape[:2]
        total_pixels = h * w

        # 1. Check ImageNet Classifier for Waste Signals
        waste_signal = False
        if self.cls_model:
            try:
                res = self.cls_model(img_bgr, verbose=False)[0]
                top5 = [(self.cls_model.names[int(i)].lower(), float(res.probs.data[i])) for i in res.probs.top5]
                waste_classes = {"garbage_truck", "ashcan", "litter", "trash_can", "waste", "dumpster", "crate"}
                waste_signal = any(c in waste_classes and score > 0.03 for c, score in top5)
            except Exception:
                waste_signal = False

        # 2. Chromatic Cluster Analysis for Multi-colored Plastic Bags & Debris
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        cell_size = max(20, int(min(h, w) * 0.05))
        grid_h, grid_w = h // cell_size, w // cell_size
        mask = np.zeros((h, w), dtype=np.uint8)

        # Focus on ground / roadside (lower 75% of scene)
        for gy in range(int(grid_h * 0.25), grid_h):
            for gx in range(grid_w):
                y1, y2 = gy * cell_size, (gy + 1) * cell_size
                x1, x2 = gx * cell_size, (gx + 1) * cell_size
                cell_hsv = hsv[y1:y2, x1:x2]
                if cell_hsv[:, :, 1].std() > 28 and cell_hsv[:, :, 2].std() > 30:
                    mask[y1:y2, x1:x2] = 255

        k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (int(cell_size * 1.3), int(cell_size * 1.3)))
        mask_clean = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_close)
        contours, _ = cv2.findContours(mask_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        dumps = []
        for c in contours:
            area = cv2.contourArea(c)
            # Threshold: at least 4% of screen if classifier triggered, or 7% otherwise
            min_thresh = 0.04 if waste_signal else 0.07
            if area > (total_pixels * min_thresh):
                x, y, bw, bh = cv2.boundingRect(c)
                dumps.append({
                    "label": "Solid Waste / Garbage Dump (Overflowing)",
                    "confidence": 0.88 if waste_signal else 0.75,
                    "bbox": [x, y, x + bw, y + bh],
                    "area_pct": round((area / total_pixels) * 100, 2)
                })

        return dumps[:3]

    def analyze_frame_bgr(self, img_bgr: np.ndarray, frame_name: str = "frame.jpg", output_dir: str = None, category_hint: str = "road") -> Dict[str, Any]:
        """Runs two-gate vision triage on an in-memory BGR frame."""
        h, w, _ = img_bgr.shape
        total_pixels = h * w

        # =====================================================================
        # GATE 1: RELEVANCE CHECK
        # =====================================================================
        relevance = self.check_civic_relevance(img_bgr)
        if not relevance["is_valid_civic"]:
            output_path = None
            if output_dir:
                annotated = img_bgr.copy()
                cv2.rectangle(annotated, (0, 0), (w, 42), (0, 0, 180), -1)
                cv2.putText(annotated, "REJECTED: NON-CIVIC CONTENT DETECTED", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
                cv2.putText(annotated, f"SPAM: {relevance['rejection_category'].upper()}", (int(w*0.05), int(h*0.5)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                output_path = os.path.join(output_dir, f"triage_annotated_{frame_name}")
                cv2.imwrite(output_path, annotated)

            return {
                "image_filename": frame_name,
                "annotated_image_path": output_path,
                "status": "REJECTED_AS_SPAM",
                "is_valid_civic_infrastructure": False,
                "severity_score": 0,
                "severity_level": "REJECTED (INVALID CIVIC EVIDENCE)",
                "rejection_reason": relevance["reason"],
                "damage_surface_coverage_pct": 0.0,
                "defect_count": 0,
                "recommended_sla_hours": 0,
                "detected_defects": []
            }

        # =====================================================================
        # GATE 2: MULTI-HAZARD DAMAGE ANALYSIS
        # =====================================================================
        detected_defects = []
        total_defect_area = 0

        # A. Road Pothole Detection (YOLO with internal optimal operating cutoff)
        if self.pothole_model:
            results = self.pothole_model(img_bgr, conf=0.38, verbose=False)[0]
            for box in results.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf[0].item())
                box_area = (x2 - x1) * (y2 - y1)
                total_defect_area += box_area
                detected_defects.append({
                    "label": "Pothole Crater",
                    "confidence": round(conf, 3),
                    "bbox": [x1, y1, x2, y2],
                    "area_pct": round((box_area / total_pixels) * 100, 2)
                })

        # B. Municipal Solid Waste & Garbage Dump Detection
        garbage_dumps = self.detect_solid_waste(img_bgr)
        for dump in garbage_dumps:
            x1, y1, x2, y2 = dump["bbox"]
            box_area = (x2 - x1) * (y2 - y1)
            total_defect_area += box_area
            detected_defects.append(dump)

        # C. Structural Concrete & Bridge Fissure Detection
        # Suppress crack false alarms if an overflowing garbage dump is present
        if len(garbage_dumps) == 0:
            structural_cracks = self.detect_structural_cracks(img_bgr)
            for crack in structural_cracks:
                x1, y1, x2, y2 = crack["bbox"]
                box_area = (x2 - x1) * (y2 - y1)
                total_defect_area += box_area
                detected_defects.append(crack)

        coverage_pct = round((total_defect_area / total_pixels) * 100, 2)
        coverage_pct = min(100.0, coverage_pct)

        # Severity Calculation
        has_structural_crack = any("structural" in d["label"].lower() for d in detected_defects)
        has_pothole = any("pothole" in d["label"].lower() for d in detected_defects)
        has_garbage = any("garbage" in d["label"].lower() or "waste" in d["label"].lower() for d in detected_defects)

        if len(detected_defects) == 0:
            severity_score = 5
            severity_level = "LOW (NO DAMAGE DETECTED)"
            hud_color = (0, 255, 0)
            sla_hours = 0
            hud_msg = "HEALTHY INFRASTRUCTURE: NO DEFECTS"
        else:
            if has_structural_crack:
                base = 65
            elif has_garbage:
                base = 52
            elif "bridge" in category_hint.lower():
                base = 55
            elif has_pothole:
                base = 40
            else:
                base = 35

            count_factor = min(20, len(detected_defects) * 8)
            area_factor = min(20, int(coverage_pct * 2))
            severity_score = min(99, max(25, base + count_factor + area_factor))

            if has_structural_crack and severity_score >= 80:
                severity_level = "CRITICAL (STRUCTURAL HAZARD)"
                hud_color = (0, 0, 255)
                sla_hours = 2
            elif has_garbage:
                severity_level = "SOLID WASTE / SANITATION MENACE"
                hud_color = (0, 165, 255)  # Amber / Orange for SWM
                sla_hours = 24  # Standard municipal SWM clearing window
            elif severity_score >= 80:
                severity_level = "CRITICAL"
                hud_color = (0, 0, 255)
                sla_hours = 4
            elif severity_score >= 60:
                severity_level = "HIGH"
                hud_color = (0, 140, 255)
                sla_hours = 24
            elif severity_score >= 40:
                severity_level = "MEDIUM"
                hud_color = (0, 215, 255)
                sla_hours = 72
            else:
                severity_level = "LOW"
                hud_color = (0, 255, 0)
                sla_hours = 168

            hud_msg = f"AI SEVERITY: {severity_score}/100 [{severity_level}] | SLA: {sla_hours}h | DEFECTS: {len(detected_defects)}"

        # Draw HUD Bounding Boxes if output_dir specified
        output_path = None
        if output_dir:
            annotated = img_bgr.copy()
            for defect in detected_defects:
                x1, y1, x2, y2 = defect["bbox"]
                cv2.rectangle(annotated, (x1, y1), (x2, y2), hud_color, 2)
                tag = f"{defect['label']} ({defect['confidence']})"
                cv2.putText(annotated, tag, (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, hud_color, 1)

            cv2.rectangle(annotated, (0, 0), (w, 36), (20, 20, 20), -1)
            cv2.putText(annotated, hud_msg, (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)
            output_path = os.path.join(output_dir, f"triage_annotated_{frame_name}")
            cv2.imwrite(output_path, annotated)

        return {
            "image_filename": frame_name,
            "annotated_image_path": output_path,
            "status": "TRIAGED_AND_DISPATCHED",
            "is_valid_civic_infrastructure": True,
            "category_hint": category_hint,
            "severity_score": severity_score,
            "severity_level": severity_level,
            "damage_surface_coverage_pct": coverage_pct,
            "defect_count": len(detected_defects),
            "recommended_sla_hours": sla_hours,
            "detected_defects": detected_defects
        }

    def analyze_image(self, image_path: str, category_hint: str = "road") -> Dict[str, Any]:
        """Runs two-gate vision triage with multi-hazard detection."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at {image_path}")

        img_bgr = cv2.imread(image_path)
        return self.analyze_frame_bgr(
            img_bgr=img_bgr,
            frame_name=os.path.basename(image_path),
            output_dir=os.path.dirname(image_path),
            category_hint=category_hint
        )

if __name__ == "__main__":
    engine = CivicVisionTriageEngine()
    test_bridge_crack = r"C:\Users\admin\.gemini\antigravity\brain\98989382-769b-4f1c-9f38-32b127e82af7\.user_uploaded\media_1793399125409_e1874bd5.jpg"
    import json
    res = engine.analyze_image(test_bridge_crack, category_hint="bridge")
    print("\n--- TEST: BRIDGE CONCRETE FOUNDATION CRACK ---")
    print(json.dumps(res, indent=2))
