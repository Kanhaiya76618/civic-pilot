"""
Civic Grievance & Infrastructure Triage System
Video Triage Engine: Frame-by-Frame Perception & Multi-Evidence Extraction.
Samples keyframes, filters camera motion blur, tracks defect continuity across
video timeline, localizes peak severity hazard frame, and transcribes embedded speech.
"""

import os
import cv2
import numpy as np
from typing import Dict, Any, List, Optional
try:
    import av
except ImportError:
    av = None

from vision_triage import CivicVisionTriageEngine
from audio_triage import CivicAudioTriageEngine

class CivicVideoTriageEngine:
    def __init__(self, vision_engine: CivicVisionTriageEngine = None, audio_engine: CivicAudioTriageEngine = None):
        self.vision_engine = vision_engine or CivicVisionTriageEngine()
        self.audio_engine = audio_engine or CivicAudioTriageEngine()

    def is_frame_blurry(self, img_bgr: np.ndarray, threshold: float = 35.0) -> bool:
        """Uses Laplacian variance to detect severe motion blur from driving or walking."""
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        variance = cv2.Laplacian(gray, cv2.CV_64F).var()
        return variance < threshold

    def extract_audio_from_video(self, video_path: str, temp_audio_path: str = None) -> Optional[str]:
        """Extracts the audio track from the video container in-memory/disk for Whisper ASR."""
        if not av or not os.path.exists(video_path):
            return None
        try:
            container = av.open(video_path)
            audio_streams = [s for s in container.streams if s.type == "audio"]
            if not audio_streams:
                return None

            if temp_audio_path is None:
                base = os.path.splitext(video_path)[0]
                temp_audio_path = f"{base}_extracted_audio.wav"

            # Transcode audio stream to 16kHz WAV
            out_container = av.open(temp_audio_path, mode="w", format="wav")
            out_stream = out_container.add_stream("pcm_s16le", rate=16000)
            out_stream.channels = 1

            for frame in container.decode(audio_streams[0]):
                frame.pts = None
                for packet in out_stream.encode(frame):
                    out_container.mux(packet)

            for packet in out_stream.encode():
                out_container.mux(packet)

            out_container.close()
            container.close()
            return temp_audio_path if os.path.exists(temp_audio_path) else None
        except Exception as e:
            # Fallback if audio extraction fails or no audio track
            return None

    def analyze_video(
        self, 
        video_path: str, 
        sample_interval_sec: float = 0.5, 
        max_frames: int = 24, 
        output_dir: str = None
    ) -> Dict[str, Any]:
        """
        End-to-End Video Triage:
        1. Reads video metadata (FPS, duration, resolution).
        2. Samples keyframes at regular intervals (skipping motion-blurred frames).
        3. Runs Gate 1 (Anti-Spam) & Gate 2 (Pothole & Concrete Crack CV) per keyframe.
        4. Identifies Peak Severity Frame and compiles an annotated Evidence HUD.
        5. Extracts and transcribes citizen voice commentary if present in audio track.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        if output_dir is None:
            output_dir = os.path.dirname(video_path)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_sec = total_frame_count / fps if fps > 0 else 0.0

        step_frames = max(1, int(fps * sample_interval_sec))
        sampled_results: List[Dict[str, Any]] = []

        curr_frame_idx = 0
        analyzed_count = 0
        peak_score = -1
        peak_frame_bgr = None
        peak_timestamp_sec = 0.0
        peak_frame_name = ""
        peak_analysis = None
        total_defects_across_video = 0
        all_defects_summary = []

        while curr_frame_idx < total_frame_count and analyzed_count < max_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, curr_frame_idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            curr_time_sec = round(curr_frame_idx / fps, 2)
            time_str = f"{int(curr_time_sec // 60):02d}:{curr_time_sec % 60:04.1f}"

            # Skip blurry frames
            if self.is_frame_blurry(frame, threshold=25.0):
                curr_frame_idx += step_frames
                continue

            frame_tag = f"frame_{curr_frame_idx:05d}_{time_str.replace(':', '_')}.jpg"
            frame_res = self.vision_engine.analyze_frame_bgr(
                img_bgr=frame,
                frame_name=frame_tag,
                output_dir=None,  # Only save peak frame
                category_hint="road"
            )

            severity = frame_res.get("severity_score", 0)
            defect_count = frame_res.get("defect_count", 0)
            total_defects_across_video += defect_count

            sampled_results.append({
                "timestamp_sec": curr_time_sec,
                "time_str": time_str,
                "frame_idx": curr_frame_idx,
                "severity_score": severity,
                "defect_count": defect_count,
                "defects": frame_res.get("detected_defects", []),
                "is_valid_civic": frame_res.get("is_valid_civic_infrastructure", True)
            })

            # Track peak severity frame
            if severity > peak_score:
                peak_score = severity
                peak_frame_bgr = frame.copy()
                peak_timestamp_sec = curr_time_sec
                peak_frame_name = frame_tag
                peak_analysis = frame_res

            analyzed_count += 1
            curr_frame_idx += step_frames

        cap.release()

        # If no frame evaluated (e.g. video was too short or corrupted)
        if peak_frame_bgr is None and total_frame_count > 0:
            cap = cv2.VideoCapture(video_path)
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                peak_frame_bgr = frame
                peak_analysis = self.vision_engine.analyze_frame_bgr(frame, frame_name="frame_0000.jpg")
                peak_score = peak_analysis.get("severity_score", 10)

        # Draw HUD Bounding Boxes on Peak Frame and save as evidence
        annotated_peak_path = None
        if peak_frame_bgr is not None and peak_analysis is not None:
            h, w, _ = peak_frame_bgr.shape
            annotated = peak_frame_bgr.copy()
            hud_color = (0, 0, 255) if peak_score >= 80 else ((0, 140, 255) if peak_score >= 60 else (0, 255, 0))

            for d in peak_analysis.get("detected_defects", []):
                x1, y1, x2, y2 = d["bbox"]
                cv2.rectangle(annotated, (x1, y1), (x2, y2), hud_color, 2)
                cv2.putText(annotated, f"{d['label']} ({d['confidence']})", (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, hud_color, 1)

            # Video HUD Header
            time_display = f"{int(peak_timestamp_sec // 60):02d}:{peak_timestamp_sec % 60:04.1f}s"
            hud_text = f"VIDEO PEAK EVIDENCE: {peak_score}/100 | TIME: {time_display} | DEFECTS: {len(peak_analysis.get('detected_defects', []))}"
            cv2.rectangle(annotated, (0, 0), (w, 36), (20, 20, 20), -1)
            cv2.putText(annotated, hud_text, (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (255, 255, 255), 1)

            video_basename = os.path.splitext(os.path.basename(video_path))[0]
            annotated_peak_path = os.path.join(output_dir, f"triage_annotated_video_{video_basename}_peak.jpg")
            cv2.imwrite(annotated_peak_path, annotated)

        # Check embedded audio commentary
        extracted_audio_res = None
        temp_audio_file = os.path.join(output_dir, f"temp_{os.path.splitext(os.path.basename(video_path))[0]}.wav")
        audio_extracted_path = self.extract_audio_from_video(video_path, temp_audio_file)
        if audio_extracted_path and os.path.exists(audio_extracted_path):
            try:
                extracted_audio_res = self.audio_engine.analyze_audio_report(audio_extracted_path)
            except Exception:
                extracted_audio_res = None
            finally:
                if os.path.exists(audio_extracted_path):
                    try:
                        os.remove(audio_extracted_path)
                    except Exception:
                        pass

        # Final synthesized SLA and priority
        final_score = peak_score if peak_score >= 0 else 20
        if extracted_audio_res and extracted_audio_res.get("severity_score", 0) > final_score:
            final_score = extracted_audio_res["severity_score"]

        sla_hours = 2 if final_score >= 80 else (24 if final_score >= 60 else (72 if final_score >= 40 else 168))

        is_valid = peak_analysis.get("is_valid_civic_infrastructure", True) if peak_analysis else True
        rejection_reason = peak_analysis.get("rejection_reason", None) if peak_analysis and not is_valid else None

        # Continuous Hazard Stretch classification
        stretch_detected = total_defects_across_video >= 3 or (len([f for f in sampled_results if f['defect_count'] > 0]) >= 3)

        return {
            "video_filename": os.path.basename(video_path),
            "duration_seconds": round(duration_sec, 1),
            "fps": round(fps, 1),
            "total_frames_in_file": total_frame_count,
            "sampled_frames_count": len(sampled_results),
            "status": "TRIAGED_AND_DISPATCHED" if is_valid else "REJECTED_AS_SPAM",
            "is_valid_civic_infrastructure": is_valid,
            "rejection_reason": rejection_reason,
            "peak_severity_score": final_score,
            "peak_timestamp_seconds": peak_timestamp_sec,
            "peak_timestamp_str": f"{int(peak_timestamp_sec // 60):02d}:{peak_timestamp_sec % 60:04.1f}",
            "annotated_peak_frame_path": annotated_peak_path,
            "aggregate_defect_count": total_defects_across_video,
            "continuous_hazard_stretch": stretch_detected,
            "recommended_sla_hours": sla_hours,
            "detected_defects": peak_analysis.get("detected_defects", []) if peak_analysis else [],
            "frame_timeline": sampled_results,
            "audio_commentary": extracted_audio_res
        }

if __name__ == "__main__":
    import json
    print("CivicVideoTriageEngine initialized successfully.")
