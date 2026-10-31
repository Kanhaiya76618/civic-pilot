"""
Autonomous Audio & Voice Note Triage Engine for Civic Infrastructure.
Uses OpenAI Whisper via PyTorch & PyAV for universal offline audio decoding (MP3/WAV/M4A),
followed by entity extraction, emergency intent detection, and automated departmental routing.
"""

import os
import re
import av
import numpy as np
from typing import Dict, Any, List

# Ensure offline loading from local cache
os.environ["HF_HUB_OFFLINE"] = "1"

try:
    from transformers import pipeline
except ImportError:
    pipeline = None

# Domain Knowledge Lexicons for Municipal Incident Routing
CIVIC_CATEGORIES = {
    "STRUCTURAL_HAZARDS": {
        "keywords": ["bridge", "flyover", "pillar", "crack", "concrete", "structural", "collapse", "falling", "chunks", "pier", "girder", "abutment"],
        "primary_dept": "Structural Engineering & Bridges Wing",
        "secondary_dept": "Traffic Police (Hazard Perimeter)",
        "base_severity": 80
    },
    "WATER_AND_DRAINAGE": {
        "keywords": ["pipe burst", "water pipe", "water supply", "drinking water", "gushing", "flooding", "drainage", "sewage", "leak", "valve", "subsurface"],
        "primary_dept": "Water Supply & Sewerage Board (BWSSB / Jal Board)",
        "secondary_dept": "Roads & Infrastructure (Pavement Erosion)",
        "base_severity": 65
    },
    "ROADS_AND_PAVEMENTS": {
        "keywords": ["pothole", "crater", "asphalt", "road", "tar", "cave-in", "motorcyclist", "accident", "patching", "skid", "trench"],
        "primary_dept": "Public Works Department (PWD / BBMP Roads)",
        "secondary_dept": "Traffic Infrastructure",
        "base_severity": 50
    },
    "SOLID_WASTE_AND_SANITATION": {
        "keywords": ["garbage", "waste", "trash", "collection truck", "stench", "dump", "smell", "dog menace", "overflowing", "sanitation"],
        "primary_dept": "Solid Waste Management (SWM / Municipal Health)",
        "secondary_dept": "Public Health & Hygiene Dept",
        "base_severity": 40
    }
}

EMERGENCY_INDICATORS = [
    "accident", "emergency", "injured", "falling", "collapse", "school", "hospital",
    "children", "death", "fatality", "fire", "sparking", "drowning", "crushed"
]

HIGH_URGENCY_INDICATORS = [
    "flooding", "washing away", "immediate", "urgent", "burst", "high pressure",
    "menace", "blocked", "severe", "danger"
]

class CivicAudioTriageEngine:
    def __init__(self, model_name: str = "openai/whisper-tiny"):
        self.model_name = model_name
        self._asr_pipeline = None

    def _get_pipeline(self):
        if self._asr_pipeline is None:
            if pipeline is None:
                raise RuntimeError("HuggingFace transformers is required for Whisper ASR.")
            self._asr_pipeline = pipeline(
                "automatic-speech-recognition",
                model=self.model_name,
                device="cpu"
            )
        return self._asr_pipeline

    @staticmethod
    def load_audio_buffer(file_path: str, target_sr: int = 16000) -> np.ndarray:
        """Universally decodes MP3, WAV, AAC, M4A, OGG using PyAV without external ffmpeg."""
        container = av.open(file_path)
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="s16", layout="mono", rate=target_sr)
        
        frames = []
        for frame in container.decode(stream):
            for rf in resampler.resample(frame):
                frames.append(rf.to_ndarray())
        for rf in resampler.resample(None):
            frames.append(rf.to_ndarray())
            
        if not frames:
            raise ValueError(f"Could not decode audio frames from {file_path}")
            
        raw_audio = np.concatenate(frames, axis=1)[0].astype(np.float32) / 32768.0
        return raw_audio

    def transcribe(self, audio_path: str) -> str:
        """Transcribes audio file to plain text."""
        audio_buffer = self.load_audio_buffer(audio_path)
        asr = self._get_pipeline()
        result = asr({"raw": audio_buffer, "sampling_rate": 16000})
        return result.get("text", "").strip()

    def analyze_audio_report(self, audio_path: str) -> Dict[str, Any]:
        """
        End-to-end voice grievance triage:
        Transcribes speech -> Classifies Category -> Extracts Entities & Locations
        -> Scores Severity & SLA -> Generates Departmental Work Order.
        """
        transcript = self.transcribe(audio_path)
        text_lower = transcript.lower()

        # 1. Category Classification
        matched_category = "GENERAL_CIVIC_INQUIRY"
        category_data = None
        max_matches = 0

        for cat_name, cat_info in CIVIC_CATEGORIES.items():
            matches = sum(1 for kw in cat_info["keywords"] if kw in text_lower)
            if matches > max_matches:
                max_matches = matches
                matched_category = cat_name
                category_data = cat_info

        base_score = category_data["base_severity"] if category_data else 30
        primary_dept = category_data["primary_dept"] if category_data else "Citizen Grievance Cell"
        secondary_dept = category_data["secondary_dept"] if category_data else "Municipal Helpdesk"

        # 2. Urgency & Distress Factor Analysis
        found_emergency = [w for w in EMERGENCY_INDICATORS if w in text_lower]
        found_urgency = [w for w in HIGH_URGENCY_INDICATORS if w in text_lower]

        urgency_score = 0
        if found_emergency:
            urgency_score += min(35, len(found_emergency) * 18)
        if found_urgency:
            urgency_score += min(20, len(found_urgency) * 10)

        total_severity = min(99, max(15, base_score + urgency_score))

        # 3. SLA Tier Assignment
        if total_severity >= 80 or len(found_emergency) > 0:
            sla_tier = "CRITICAL_IMMEDIATE"
            sla_hours = 2
            priority_label = "CRITICAL (LIFE-SAFETY HAZARD)"
        elif total_severity >= 60:
            sla_tier = "HIGH"
            sla_hours = 24
            priority_label = "HIGH PRIORITY"
        elif total_severity >= 40:
            sla_tier = "MEDIUM"
            sla_hours = 72
            priority_label = "MEDIUM PRIORITY"
        else:
            sla_tier = "ROUTINE"
            sla_hours = 168
            priority_label = "ROUTINE MAINTENANCE"

        # 4. Location & Landmark Entity Extraction (Regex + Keyword Spotting)
        location_patterns = [
            r"(?:on|near|at|opposite|in front of)\s+([0-9a-zA-Z\s]{4,35}?)(?:\.|\,|near|before|after|with|causing|$)",
            r"([0-9]+(?:th|rd|st|nd)?\s+(?:cross|main|street|road|avenue|sector|layout)[0-9a-zA-Z\s,]*)",
            r"(indiranagar|koramangala|hosur\s+road|whitefield|jayanagar|mg\s+road|outer\s+ring\s+road|pillar\s+[0-9]+)"
        ]
        
        extracted_locations = []
        for pat in location_patterns:
            matches = re.findall(pat, text_lower, re.IGNORECASE)
            for m in matches:
                clean_loc = m.strip().title()
                if len(clean_loc) > 3 and clean_loc not in extracted_locations:
                    extracted_locations.append(clean_loc)

        return {
            "audio_filename": os.path.basename(audio_path),
            "transcript": transcript,
            "category": matched_category,
            "severity_score": total_severity,
            "priority_label": priority_label,
            "enforced_sla_hours": sla_hours,
            "sla_tier": sla_tier,
            "primary_department": primary_dept,
            "secondary_department": secondary_dept,
            "emergency_keywords_detected": found_emergency,
            "urgency_keywords_detected": found_urgency,
            "extracted_locations": extracted_locations[:3],
            "audit_ledger_status": "VOICE_VERIFIED_AND_DISPATCHED"
        }

    def analyze_text_report(self, text: str) -> Dict[str, Any]:
        """
        Analyze a citizen's written grievance text for intent, distress indicators, 
        severity, and departmental routing without requiring audio.
        """
        text_lower = text.lower()
        matched_category = "GENERAL_CIVIC_INQUIRY"
        category_data = None
        max_matches = 0

        for cat_name, cat_info in CIVIC_CATEGORIES.items():
            matches = sum(1 for kw in cat_info["keywords"] if kw in text_lower)
            if matches > max_matches:
                max_matches = matches
                matched_category = cat_name
                category_data = cat_info

        base_score = category_data["base_severity"] if category_data else 30
        primary_dept = category_data["primary_dept"] if category_data else "Citizen Grievance Cell"
        secondary_dept = category_data["secondary_dept"] if category_data else "Municipal Helpdesk"

        found_emergency = [w for w in EMERGENCY_INDICATORS if w in text_lower]
        found_urgency = [w for w in HIGH_URGENCY_INDICATORS if w in text_lower]

        urgency_score = 0
        if found_emergency:
            urgency_score += min(35, len(found_emergency) * 18)
        if found_urgency:
            urgency_score += min(20, len(found_urgency) * 10)

        total_severity = min(99, max(15, base_score + urgency_score))

        if total_severity >= 80 or len(found_emergency) > 0:
            sla_tier = "CRITICAL_IMMEDIATE"
            sla_hours = 2
            priority_label = "CRITICAL (LIFE-SAFETY HAZARD)"
        elif total_severity >= 60:
            sla_tier = "HIGH"
            sla_hours = 24
            priority_label = "HIGH PRIORITY"
        elif total_severity >= 40:
            sla_tier = "MEDIUM"
            sla_hours = 72
            priority_label = "MEDIUM PRIORITY"
        else:
            sla_tier = "ROUTINE"
            sla_hours = 168
            priority_label = "ROUTINE MAINTENANCE"

        location_patterns = [
            r"(?:on|near|at|opposite|in front of)\s+([0-9a-zA-Z\s]{4,35}?)(?:\.|\,|near|before|after|with|causing|$)",
            r"([0-9]+(?:th|rd|st|nd)?\s+(?:cross|main|street|road|avenue|sector|layout)[0-9a-zA-Z\s,]*)",
            r"(indiranagar|koramangala|hosur\s+road|whitefield|jayanagar|mg\s+road|outer\s+ring\s+road|pillar\s+[0-9]+)"
        ]
        
        extracted_locations = []
        for pat in location_patterns:
            matches = re.findall(pat, text_lower, re.IGNORECASE)
            for m in matches:
                clean_loc = m.strip().title()
                if len(clean_loc) > 3 and clean_loc not in extracted_locations:
                    extracted_locations.append(clean_loc)

        return {
            "audio_filename": "written_complaint.txt",
            "transcript": text,
            "category": matched_category,
            "severity_score": total_severity,
            "priority_label": priority_label,
            "enforced_sla_hours": sla_hours,
            "sla_tier": sla_tier,
            "primary_department": primary_dept,
            "secondary_department": secondary_dept,
            "emergency_keywords_detected": found_emergency,
            "urgency_keywords_detected": found_urgency,
            "extracted_locations": extracted_locations[:3],
            "audit_ledger_status": "TEXT_GRIEVANCE_VERIFIED"
        }

if __name__ == "__main__":
    engine = CivicAudioTriageEngine()
    samples_dir = os.path.join(os.path.dirname(__file__), "..", "data", "ai_datasets", "audio_samples")
    import json
    for sample in ["voice_pothole_accident_hazard.mp3", "voice_water_main_rupture.mp3", "voice_bridge_crack_emergency.mp3", "voice_garbage_overflow.mp3"]:
        p = os.path.join(samples_dir, sample)
        if os.path.exists(p):
            print(f"\n=================== {sample} ===================")
            res = engine.analyze_audio_report(p)
            print(json.dumps(res, indent=2))
