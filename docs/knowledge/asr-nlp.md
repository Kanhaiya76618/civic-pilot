# Skill Note: Audio ASR (Whisper) & Civic Lexicon Intent Mapping

## Overview & Architecture
Citizen voice notes and audio demuxed from video recordings provide rich qualitative evidence regarding civic hazards (e.g., "water pipe burst flooding the road", "deep pothole causing bike skids").
The audio pipeline operates entirely offline:
$$\text{Audio Demux (PyAV / ffmpeg)} \longrightarrow \text{ASR Transcription (Whisper-tiny)} \longrightarrow \text{Lexicon Intent & Severity Mapping}$$
It maps transcribed text into municipal departmental routes and calculates an audio-derived severity score.

---

## 1. Patterns
- **Universal Audio Demux**: Use `av` (PyAV) or `ffmpeg` to extract mono 16 kHz audio streams from any container format (`.mp3`, `.wav`, `.m4a`, `.mp4`).
- **Offline Whisper Pipeline**: Pre-cache Whisper-tiny weights and set `HF_HUB_OFFLINE=1` to guarantee instant offline transcription without external network dependencies.
- **Lexicon Keyword Triage**: Municipal issues in Indian cities map directly to specialized departments:
  - `ROADS_AND_PAVEMENTS`: "pothole", "crater", "asphalt", "skid" $\to$ PWD / Road Infrastructure
  - `WATER_AND_DRAINAGE`: "water main", "leak", "pipe burst", "sewage", "flooding" $\to$ Water Supply & Sewerage Board
  - `STRUCTURAL_HAZARDS`: "bridge crack", "flyover", "pillar fracture", "collapse" $\to$ Structural Engineering & Traffic Police
  - `SANITATION`: "garbage overflow", "trash", "dumping" $\to$ Solid Waste Management
- **Emergency Severity Multiplier**: Boost score by +20 if urgent keywords appear ("accident", "hospital", "school", "fatal", "hazard").

---

## 2. Common Pitfalls
1. **Audio Sampling Mismatch**: Whisper requires exactly 16,000 Hz single-channel (mono) audio floats normalized between $[-1.0, 1.0]$. Passing 44.1 kHz stereo without resampling produces gibberish or tensor dimension errors.
2. **Heavy Whisper Models**: Larger Whisper variants (`small`, `medium`) introduce significant inference latency on CPU (5–15 seconds). `whisper-tiny` processes short clips in <1 second with sufficient accuracy for keyword matching.
3. **Empty Audio Crashes**: Silent or zero-length audio clips cause HuggingFace pipeline or Whisper exceptions unless guarded with length and energy thresholds.

---

## 3. Minimal Working Code Skeleton

```python
import io
import re
import av
import numpy as np

CIVIC_LEXICON = {
    "STRUCTURAL_HAZARDS": {
        "keywords": ["bridge", "flyover", "pillar", "crack", "concrete", "collapse", "pier"],
        "dept": "Structural Engineering & Bridges Wing",
        "base_severity": 80
    },
    "WATER_AND_DRAINAGE": {
        "keywords": ["pipe burst", "water pipe", "flooding", "drainage", "sewage", "leak"],
        "dept": "Water Supply & Sewerage Board",
        "base_severity": 65
    },
    "ROADS_AND_PAVEMENTS": {
        "keywords": ["pothole", "crater", "asphalt", "road", "tar", "skid", "cave-in"],
        "dept": "Public Works Department",
        "base_severity": 50
    }
}

def decode_audio_to_16k_mono(audio_bytes: bytes) -> np.ndarray:
    """Decodes arbitrary audio bytes to 16kHz mono float32 numpy array."""
    container = av.open(io.BytesIO(audio_bytes))
    stream = next(s for s in container.streams if s.type == "audio")
    resampler = av.AudioResampler(format="flt2", layout="mono", rate=16000)
    
    frames = []
    for frame in container.decode(stream):
        for resampled in resampler.resample(frame):
            frames.append(resampled.to_ndarray())
            
    if not frames:
        return np.array([], dtype=np.float32)
    return np.concatenate(frames, axis=1).squeeze(0)

def match_civic_lexicon(transcript: str) -> dict:
    """Classifies department and calculates audio severity from transcript text."""
    text = transcript.lower()
    best_match = None
    max_hits = 0
    
    for cat, info in CIVIC_LEXICON.items():
        hits = sum(1 for kw in info["keywords"] if re.search(rf"\b{re.escape(kw)}\b", text))
        if hits > max_hits:
            max_hits = hits
            best_match = (cat, info)
            
    if not best_match:
        return {"category": "GENERAL_CIVIC", "department": "Municipal Helpdesk", "severity": 30}
        
    cat, info = best_match
    severity = info["base_severity"] + min(20, max_hits * 5)
    if any(em in text for em in ["urgent", "danger", "accident", "emergency", "school"]):
        severity = min(100, severity + 15)
        
    return {"category": cat, "department": info["dept"], "severity": severity, "keyword_matches": max_hits}
```

---

## 4. Verified Source Links
- OpenAI Whisper GitHub & Model Specs: https://github.com/openai/whisper
- PyAV Documentation: https://pyav.org/docs/develop/
- Hugging Face Transformers ASR Pipeline: https://huggingface.co/docs/transformers/main_classes/pipelines#transformers.AutomaticSpeechRecognitionPipeline
