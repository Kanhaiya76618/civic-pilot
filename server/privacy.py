"""Privacy for photos the public can see (proof-of-repair photos on the accountability board).

Every detected face is blurred and the photo is re-encoded, which also drops its metadata (EXIF, including any GPS
position of the officer's phone). Faces are found with YuNet (OpenCV's face detector; model from opencv_zoo, MIT
licence). It is good, not perfect, so the board says "detected faces are blurred", never "all faces". Number plates
are not detected.
"""

from pathlib import Path

import cv2
import numpy as np

MODEL = Path(__file__).parent / "models" / "face_detection_yunet_2023mar.onnx"
MIN_SCORE = 0.6


class UnreadableImage(ValueError):
    pass


def faces(img: np.ndarray) -> list[tuple[int, int, int, int]]:
    h, w = img.shape[:2]
    detector = cv2.FaceDetectorYN.create(str(MODEL), "", (w, h), score_threshold=MIN_SCORE)
    _, found = detector.detect(img)
    return [] if found is None else [tuple(int(v) for v in row[:4]) for row in found]


def blur_faces(data: bytes, max_side: int = 2000) -> tuple[bytes, int]:
    """JPEG bytes with every detected face blurred, and how many were blurred."""
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise UnreadableImage("The photo could not be read. Please upload a JPEG or PNG.")
    scale = max_side / max(img.shape[:2])
    if scale < 1:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    boxes = faces(img)
    for (x, y, w, h) in boxes:
        pad = int(0.25 * max(w, h))
        x0, y0, x1, y1 = max(0, x - pad), max(0, y - pad), min(img.shape[1], x + w + pad), min(img.shape[0], y + h + pad)
        if x1 <= x0 or y1 <= y0:
            continue
        region = img[y0:y1, x0:x1]
        # Pixelate to a few blocks, then soften the blocks: nothing of the face is left to recognise.
        small = cv2.resize(region, (6, max(1, round(6 * region.shape[0] / region.shape[1]))), interpolation=cv2.INTER_AREA)
        blocks = cv2.resize(small, (region.shape[1], region.shape[0]), interpolation=cv2.INTER_NEAREST)
        k = max(15, (max(region.shape[:2]) // 4) | 1)
        img[y0:y1, x0:x1] = cv2.GaussianBlur(blocks, (k, k), 0)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise UnreadableImage("The photo could not be processed. Please upload a JPEG or PNG.")
    return buf.tobytes(), len(boxes)
