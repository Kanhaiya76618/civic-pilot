# Skill Note: Computer Vision Triage Engine (YOLOv8, Crack Morphology & Video Keyframes)

## Overview & Architecture
The vision triage engine processes images and citizen video footage through a sequential pipeline:
$$\text{Spam / OOD Gate (YOLO-CLS)} \longrightarrow \text{Pothole Detector (YOLOv8)} \longrightarrow \text{Crack Morphology (OpenCV)} \longrightarrow \text{Severity Scoring}$$
Video triage runs demuxing, drops motion-blurred frames via variance of the Laplacian, and extracts the peak severity keyframe to avoid redundant inference.

---

## 1. Patterns
- **Gate 1 Spam Filtering**: Run a lightweight classifier (e.g. `yolov8n-cls`). If top classes belong to indoor/food/pet categories with high confidence (>0.15), reject early before running detection. If confidence is uncertain (0.10–0.15), route to `MANUAL_REVIEW` queue rather than hard rejection.
- **Gate 2A Pothole Detection**: YOLOv8 model outputs bounding boxes and confidence scores. The hazard score scales with normalized bounding box area relative to the frame size and confidence.
- **Gate 2B Structural Crack Morphology**: Use OpenCV morphological Black-Hat / Top-Hat transforms (`cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)`) followed by Otsu adaptive thresholding to isolate linear dark fissures on concrete/asphalt.
- **Video Keyframe Selection & Blur Filter**: Compute Laplacian variance:
  $$\text{Var}(\nabla^2 I) < \text{Threshold} \implies \text{Blurry, skip}$$
  Accumulate scores across sharp keyframes (e.g. 1 frame every 0.5s) and retain the peak keyframe as the primary visual evidence.

---

## 2. Common Pitfalls
1. **Hard Rejection on Edge Cases**: Overly strict spam gate thresholds reject real photos of potholes that happen to contain a car tire or foot. Use an "Uncertain → Manual Review" fallback.
2. **BGR vs RGB Inconsistency**: OpenCV reads images as BGR, while PyTorch / PIL / matplotlib expect RGB. Passing BGR directly into some models causes color distortion and lowered recall.
3. **Memory Accumulation during Video Processing**: Reading all video frames into a Python list exhausts RAM. Stream frames iteratively using `cv2.VideoCapture` and release immediately.

---

## 3. Minimal Working Code Skeleton

```python
import cv2
import numpy as np

def is_frame_sharp(gray_frame: np.ndarray, min_variance: float = 100.0) -> bool:
    """Laplacian blur filter: variance of Laplacian detects sharpness."""
    var = cv2.Laplacian(gray_frame, cv2.CV_64F).var()
    return var >= min_variance

def analyze_crack_morphology(gray_frame: np.ndarray) -> dict:
    """Detects structural concrete fissures using morphological black-hat transform."""
    # Rectangular kernel highlights linear cracks
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    blackhat = cv2.morphologyEx(gray_frame, cv2.MORPH_BLACKHAT, kernel)
    
    # Otsu thresholding
    _, thresh = cv2.threshold(blackhat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    crack_pixels = np.count_nonzero(thresh)
    total_pixels = thresh.size
    crack_ratio = crack_pixels / total_pixels
    
    return {
        "crack_detected": crack_ratio > 0.005,
        "crack_ratio": float(crack_ratio),
        "morph_severity": min(100, int(crack_ratio * 2000))
    }

def process_video_evidence(video_path: str, sample_fps: int = 2) -> dict:
    """Extracts sharp keyframes from video and finds peak severity frame."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = int(fps / sample_fps)
    
    frame_idx = 0
    sharp_frames = []
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % frame_interval == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if is_frame_sharp(gray):
                crack_res = analyze_crack_morphology(gray)
                sharp_frames.append((frame_idx, crack_res["morph_severity"], frame))
        frame_idx += 1
    cap.release()
    
    if not sharp_frames:
        return {"success": False, "peak_severity": 0, "peak_frame": None}
        
    sharp_frames.sort(key=lambda x: x[1], reverse=True)
    peak_idx, peak_score, peak_bgr = sharp_frames[0]
    return {"success": True, "peak_severity": peak_score, "frame_index": peak_idx, "frame": peak_bgr}
```

---

## 4. Verified Source Links
- Ultralytics YOLOv8 Documentation: https://docs.ultralytics.com/
- OpenCV Morphological Transformations: https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html
- OpenCV Image Gradients & Laplacian: https://docs.opencv.org/4.x/d5/d0f/tutorial_py_gradients.html
