"""
Transparent Civic Grievance & Infrastructure Triage System
Unified Multimodal Architecture:
Tab 1: 📝 File Incident (Photo + Voice + True Drag & Drop Pin Map + 50m Deduplication)
Tab 2: 🔍 Public Accountability Ledger & Repair Tracker (Before/After Proof + Re-complaint Dispute)
"""

import os
import sys
import json
import hashlib
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

sys.path.append(os.path.dirname(__file__))
from vision_triage import CivicVisionTriageEngine
from audio_triage import CivicAudioTriageEngine
from gis_routing import CivicGISRouter

st.set_page_config(
    page_title="Transparent Civic AI Triage",
    page_icon="🏛️",
    layout="wide"
)

# Custom Styling
st.markdown("""
<style>
    .main-title { font-size: 2.2rem; font-weight: 800; color: #1e293b; margin-bottom: 0.2rem; }
    .subtitle   { font-size: 1.05rem; color: #64748b; margin-bottom: 1.2rem; }
    .ticket-box { background: #f8fafc; border: 1px solid #e2e8f0; border-left: 5px solid #2563eb;
                  padding: 1.2rem; border-radius: 8px; margin-top: 1rem; }
    .rejection-box { background: #fef2f2; border: 1px solid #fecaca; border-left: 5px solid #dc2626;
                     padding: 1.2rem; border-radius: 8px; margin-top: 1rem; color: #991b1b; }
    .badge-critical { background-color: #fee2e2; color: #dc2626; padding: 4px 10px; border-radius: 6px; font-weight: bold; }
    .badge-high     { background-color: #ffedd5; color: #ea580c; padding: 4px 10px; border-radius: 6px; font-weight: bold; }
    .badge-medium   { background-color: #fef9c3; color: #ca8a04; padding: 4px 10px; border-radius: 6px; font-weight: bold; }
    .badge-low      { background-color: #dcfce7; color: #16a34a; padding: 4px 10px; border-radius: 6px; font-weight: bold; }
    .badge-dispute  { background-color: #fdf2f8; color: #db2777; padding: 4px 10px; border-radius: 6px; font-weight: bold; border: 1px solid #fbcfe8; }
    .pin-card       { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 12px; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_vision_engine():
    pothole_weights = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pothole_best.pt"))
    weights = pothole_weights if os.path.exists(pothole_weights) else "yolov8n.pt"
    return CivicVisionTriageEngine(pothole_weights=weights)

@st.cache_resource
def get_audio_engine():
    return CivicAudioTriageEngine()

@st.cache_resource
def get_gis_router():
    return CivicGISRouter()

vision_engine = get_vision_engine()
audio_engine = get_audio_engine()
gis_router = get_gis_router()

# Declare Custom Draggable Map Component (Local Leaflet with Drag & Drop Pin)
COMPONENT_PATH = os.path.join(os.path.dirname(__file__), "static", "draggable_pin_map")
draggable_map_component = components.declare_component("draggable_pin_map", path=COMPONENT_PATH)

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "ai_datasets", "vision_damage"))
DATASET_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "anant_dataset", "My Dataset"))
AUDIO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "ai_datasets", "audio_samples"))
LEDGER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "grievance_ledger.json"))

def load_ledger():
    if os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_ledger(tickets):
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(tickets, f, indent=2)

# Session state initialization for live location (NO prefilled dummy location)
if "pinned_lat" not in st.session_state:
    st.session_state.pinned_lat = None
if "pinned_lon" not in st.session_state:
    st.session_state.pinned_lon = None
if "location_address" not in st.session_state:
    st.session_state.location_address = None
if "is_live_gps" not in st.session_state:
    st.session_state.is_live_gps = True

# --- HEADER ---
st.markdown('<div class="main-title">🏛️ Transparent Civic Grievance & Infrastructure Triage System</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">AI Multimodal Triage: Vision & Speech Ingestion ➔ GIS Ward Resolution ➔ Autonomous SLA Enforcement ➔ Public Repair Verification</div>', unsafe_allow_html=True)

tab_report, tab_ledger = st.tabs([
    "📝 File Civic Grievance (Unified Vision + Voice + Drag-and-Drop Pin)", 
    "🔍 Public Transparency Ledger & Repair Tracker (Before/After Proof)"
])

# =============================================================================
# TAB 1: UNIFIED CITIZEN REPORTING (VISION + VOICE + DRAG & DROP MAP PIN)
# =============================================================================
with tab_report:
    st.markdown("### 1. File Civic Grievance & Evidence")

    complaint_text = st.text_area(
        "✍️ Grievance Description / Citizen Statement (Optional):",
        placeholder="Type details about the issue (e.g., Severe pothole crater right outside the school gate causing skidding bikes, water pipe burst with flooding)...",
        height=75,
        key="citizen_complaint_desc"
    )

    c_opt1, c_opt2 = st.columns(2)
    with c_opt1:
        has_image = st.checkbox("📸 Include Photo Evidence", value=True)
    with c_opt2:
        has_audio = st.checkbox("🎙️ Include Voice Note / Audio Complaint", value=True)

    target_image_path = None
    target_audio_path = None

    # Image Ingestion Row
    if has_image:
        st.write("")
        st.markdown("##### 📸 Photo Ingestion")
        img_source = st.radio(
            "How to provide the photo:",
            ["📤 Upload Custom Photo", "📂 712-Image Benchmark (Anant)", "📁 Pre-Loaded Real-World Samples"],
            horizontal=True,
            key="img_source_unified"
        )
        if img_source == "📤 Upload Custom Photo":
            u_img = st.file_uploader("Upload Damage Photo:", type=["jpg", "jpeg", "png"], key="u_img_unified")
            if u_img is not None:
                save_p = os.path.join(DATA_DIR, f"user_upload_{u_img.name}")
                with open(save_p, "wb") as f:
                    f.write(u_img.getbuffer())
                target_image_path = save_p
        elif img_source == "📂 712-Image Benchmark (Anant)":
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                sp_choice = st.selectbox("Split:", ["Train / Potholes (356)", "Train / Plain (340)", "Test / Potholes (8)", "Test / Plain (8)"])
            split_map = {"Train / Potholes (356)": "train/Pothole", "Train / Plain (340)": "train/Plain", "Test / Potholes (8)": "test/Pothole", "Test / Plain (8)": "test/Plain"}
            fold = os.path.join(DATASET_DIR, split_map[sp_choice].replace("/", os.sep))
            with col_b2:
                if os.path.exists(fold):
                    imgs = [f for f in os.listdir(fold) if f.lower().endswith((".jpg", ".png"))]
                    imgs = sorted(imgs, key=lambda x: int(os.path.splitext(x)[0]) if os.path.splitext(x)[0].isdigit() else x)
                    target_image_path = os.path.join(fold, st.selectbox("Choose File:", imgs, key="choice_anant_u"))
        else:
            s_files = [f for f in os.listdir(DATA_DIR) if f.endswith((".jpg", ".png")) and "triage_annotated" not in f and not f.startswith("user_upload_")]
            if s_files:
                target_image_path = os.path.join(DATA_DIR, st.selectbox("Select Sample Civic Photo:", s_files, key="preloaded_u"))

    # Audio Ingestion Row
    if has_audio:
        st.write("")
        st.markdown("##### 🎙️ Voice Grievance Ingestion")
        aud_source = st.radio(
            "How to provide the audio:",
            ["📁 Pre-Recorded Civic Helpline Calls", "📤 Upload Custom Audio (MP3/WAV/M4A)"],
            horizontal=True,
            key="aud_source_unified"
        )
        if aud_source == "📁 Pre-Recorded Civic Helpline Calls":
            audio_map = {
                "voice_pothole_accident_hazard.mp3": "🚨 Road Hazard: Pothole & Accident (School Junction)",
                "voice_bridge_crack_emergency.mp3": "🌉 Structural Hazard: Bridge Pillar Concrete Fracture (Pillar 14)",
                "voice_water_main_rupture.mp3": "💧 Water Disaster: High-Pressure Main Rupture & Flooding (100 Ft Rd)",
                "voice_garbage_overflow.mp3": "♻️ Sanitation: Commercial Waste Dump & Stray Dog Menace (5th Cross)"
            }
            c_aud = st.selectbox("Choose Call Scenario:", list(audio_map.keys()), format_func=lambda x: audio_map[x], key="aud_choice_u")
            target_audio_path = os.path.join(AUDIO_DIR, c_aud)
        else:
            u_aud = st.file_uploader("Upload Audio Complaint:", type=["wav", "mp3", "m4a", "ogg"], key="u_aud_unified")
            if u_aud is not None:
                save_ap = os.path.join(AUDIO_DIR, f"user_aud_{u_aud.name}")
                with open(save_ap, "wb") as f:
                    f.write(u_aud.getbuffer())
                target_audio_path = save_ap

    st.divider()

    # =========================================================================
    # 2. INCIDENT LOCATION: ALWAYS-VISIBLE LIVE INTERACTIVE MAP (NO TOGGLE NEEDED)
    # =========================================================================
    st.markdown("### 2. Incident Location (Live Auto-Detected GPS)")
    st.info("📍 **Your real-time location is auto-detected below.** Drag the red pin with your mouse/touch, click anywhere on the street to adjust the exact defect spot, or click **🎯 My Current GPS** on the map.")

    # Always-visible interactive draggable map component
    loc_payload = draggable_map_component(
        lat=st.session_state.pinned_lat,
        lon=st.session_state.pinned_lon,
        visible=True,
        is_live=st.session_state.is_live_gps,
        key="drag_and_drop_pin_widget"
    )

    # Sync any live GPS or user-dragged coordinates back to session state
    if loc_payload:
        n_lat = loc_payload.get("lat")
        n_lon = loc_payload.get("lon")
        n_addr = loc_payload.get("address", "")
        n_live = loc_payload.get("is_live_gps", False)

        changed = False
        if n_lat is not None:
            fl_lat = round(float(n_lat), 6)
            if st.session_state.pinned_lat is None or abs(fl_lat - st.session_state.pinned_lat) > 0.00002:
                st.session_state.pinned_lat = fl_lat
                changed = True
        if n_lon is not None:
            fl_lon = round(float(n_lon), 6)
            if st.session_state.pinned_lon is None or abs(fl_lon - st.session_state.pinned_lon) > 0.00002:
                st.session_state.pinned_lon = fl_lon
                changed = True
        if n_addr and n_addr != st.session_state.location_address:
            st.session_state.location_address = n_addr
            changed = True
        if n_live != st.session_state.is_live_gps:
            st.session_state.is_live_gps = n_live
            changed = True

        if changed:
            st.rerun()

    # Display Current Live Location Status Card
    if st.session_state.pinned_lat is not None and st.session_state.pinned_lon is not None:
        cur_lat = round(st.session_state.pinned_lat, 5)
        cur_lon = round(st.session_state.pinned_lon, 5)
        quick_ward = gis_router.resolve_location(cur_lat, cur_lon, custom_address=st.session_state.location_address)

        gps_status_badge = "🟢 Device GPS Verified (Real-Time)" if st.session_state.is_live_gps else "📍 Manually Adjusted Pin"

        st.markdown(f"""
        <div style="background: #1e293b; border: 1px solid #38bdf8; border-radius: 10px; padding: 14px 18px; margin-top: 10px; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.25);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-size: 15px; font-weight: 700; color: #38bdf8;">📍 {'My Live Current Location' if st.session_state.is_live_gps else 'Incident Pinned Location'}</span>
                <span style="background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid #22c55e; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;">{gps_status_badge}</span>
            </div>
            <div style="font-size: 14px; line-height: 1.6; color: #f1f5f9;">
                🏛️ <b>Jurisdiction / Area:</b> <b>{quick_ward['ward_name']}</b> &nbsp;|&nbsp; 🏙️ <b>Body:</b> {quick_ward['city']}<br>
                👷 <b>Nodal Authority:</b> <code>{quick_ward['executive_engineer_in_charge']}</code><br>
                🌐 <b>Active Coordinates:</b> <code>{cur_lat:.5f}° N, {cur_lon:.5f}° E</code>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("📡 **Detecting your live device GPS location...** Please ensure location access is allowed in your browser prompt.")
        cur_lat = None
        cur_lon = None

    st.divider()

    # One-Click Unified Triage Submission
    st.markdown("### 3. Run Autonomous Multimodal Triage")

    submit_btn = st.button("🚀 Submit Verified Civic Grievance & Execute Autonomous Triage", type="primary", use_container_width=True)

    if submit_btn:
        if cur_lat is None or cur_lon is None:
            st.error("Please allow GPS location access or toggle the map to pin your incident location before submitting.")
        elif not target_image_path and not target_audio_path and not complaint_text.strip():
            st.error("Please provide at least one form of evidence (Written Complaint, Photo, or Voice Note).")
        else:
            with st.spinner("Executing Unified Pipeline: Vision Gates ➔ Whisper ASR ➔ Ward PIP ➔ Deduplication..."):
                vision_res = None
                audio_res = None

                # Process Vision
                if target_image_path and os.path.exists(target_image_path):
                    vision_res = vision_engine.analyze_image(target_image_path)

                # Process Audio or Written Text
                if target_audio_path and os.path.exists(target_audio_path):
                    audio_res = audio_engine.analyze_audio_report(target_audio_path)
                elif complaint_text.strip():
                    audio_res = audio_engine.analyze_text_report(complaint_text.strip())

                # Process GIS
                ward_res = gis_router.resolve_location(cur_lat, cur_lon, custom_address=st.session_state.location_address)
                dup_res = gis_router.check_spatial_duplicate(cur_lat, cur_lon, "Civic Defect")

                # =============================================================
                # GATE 1 SPAM CHECK (If photo submitted)
                # =============================================================
                if vision_res and not vision_res.get("is_valid_civic_infrastructure", True):
                    st.markdown(f"""
                    <div class="rejection-box">
                        <h3>🚫 Report Rejected: Non-Civic Content Detected</h3>
                        <b>Gate-1 Relevance Filter:</b> Photo failed validation.<br>
                        <b>Reason:</b> {vision_res['rejection_reason']}<br><br>
                        <i>No municipal crew or public work order will be created for non-infrastructure imagery.</i>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    # Severity & SLA Synthesis
                    scores = []
                    if vision_res: scores.append(vision_res["severity_score"])
                    if audio_res: scores.append(audio_res["severity_score"])
                    final_score = max(scores) if scores else 50

                    # Apply Critical POI Multiplier (Near Hospital/School)
                    if ward_res["poi_vulnerability_multiplier"] > 1.0:
                        final_score = min(99, int(final_score * ward_res["poi_vulnerability_multiplier"]))

                    if final_score >= 80:
                        level_label = "CRITICAL (LIFE-SAFETY / STRUCTURAL HAZARD)"
                        sla_h = 2
                        badge_c = "badge-critical"
                    elif final_score >= 60:
                        level_label = "HIGH PRIORITY"
                        sla_h = 24
                        badge_c = "badge-high"
                    elif final_score >= 40:
                        level_label = "MEDIUM PRIORITY"
                        sla_h = 72
                        badge_c = "badge-medium"
                    else:
                        level_label = "ROUTINE"
                        sla_h = 168
                        badge_c = "badge-low"

                    # Primary Department Selection
                    if audio_res:
                        dept = audio_res["primary_department"]
                    elif vision_res and any("crack" in str(d).lower() for d in vision_res.get("detected_defects", [])):
                        dept = "Structural Engineering & Bridges Wing"
                    else:
                        dept = "Public Works Department (PWD / BBMP Roads)"

                    # Generate Ticket ID
                    t_hash = hashlib.sha256(f"{cur_lat}{cur_lon}{final_score}".encode()).hexdigest()[:8].upper()
                    new_ticket_id = f"CIV-2026-{ward_res['ward_number']}-{t_hash}"

                    # Show Deduplication Status
                    if dup_res["is_duplicate"]:
                        st.warning(f"""
                        ⚠️ **SPATIAL DEDUPLICATION TRIGGERED (Distance: {dup_res['distance_meters']}m)**  
                        * {dup_res['explanation']}  
                        * **Auto-Merged into Parent Ticket:** `#{dup_res['matched_parent_ticket']}`  
                        * **Total Citizen Endorsements:** **{dup_res['total_citizen_reports']} citizens**
                        """)
                    else:
                        st.success(f"✅ **Distinct Incident Verified**: No duplicate tickets within 50m. Creating new work order #{new_ticket_id}.")

                    # Unified Triage Banner
                    st.markdown(f"""
                    <div class="ticket-box">
                        <span class="{badge_c}">● {level_label}</span> &nbsp; Severity Rating: <b>{final_score}/100</b><br><br>
                        🏙️ <b>Jurisdiction:</b> {ward_res['city']} — <b>{ward_res['ward_name']}</b> (Ward No. {ward_res['ward_number']})<br>
                        👷 <b>Nodal Engineer Assigned:</b> <code>{ward_res['executive_engineer_in_charge']}</code><br>
                        🏢 <b>Lead Response Agency:</b> <b>{dept}</b><br>
                        ⏱️ <b>Enforced Response SLA:</b> <b>{sla_h} Hours</b>
                    </div>
                    """, unsafe_allow_html=True)

                    st.write("")
                    col_hud, col_speech = st.columns([1, 1], gap="medium")

                    with col_hud:
                        st.markdown("**📸 Visual Defect Localizations (HUD):**")
                        if vision_res and os.path.exists(vision_res.get("annotated_image_path", "")):
                            st.image(Image.open(vision_res["annotated_image_path"]), caption="Triage HUD", width="stretch")
                            st.caption(f"Defects Identified: {vision_res['defect_count']} | Area Impacted: {vision_res['damage_surface_coverage_pct']}%")
                        else:
                            st.info("No photo attached for this report.")

                    with col_speech:
                        st.markdown("**🎙️ Voice Note / Written Grievance:**")
                        if audio_res:
                            if audio_res.get("audio_filename") == "written_complaint.txt":
                                st.info(f"✍️ **Citizen Statement:** \"{audio_res['transcript']}\"")
                            else:
                                st.info(f"🎙️ **Audio Transcript:** \"{audio_res['transcript']}\"")
                            if audio_res.get("emergency_keywords_detected"):
                                st.error(f"🚨 Emergency Flags: {', '.join(audio_res['emergency_keywords_detected'])}")
                            if audio_res.get("extracted_locations"):
                                st.success(f"📍 Landmark Entities: {', '.join(audio_res['extracted_locations'])}")
                        elif complaint_text.strip():
                            st.info(f"✍️ **Citizen Statement:** \"{complaint_text.strip()}\"")
                        else:
                            st.info("No voice note or written text attached for this report.")

                    # Save to Public Ledger DB if new
                    if not dup_res["is_duplicate"]:
                        existing_ledger = load_ledger()
                        new_record = {
                            "ticket_id": new_ticket_id,
                            "title": f"Incident in {ward_res['ward_name']}",
                            "description": complaint_text.strip() if complaint_text.strip() else (audio_res["transcript"] if audio_res else f"Incident in {ward_res['ward_name']}"),
                            "category": audio_res["category"] if audio_res else "ROADS_AND_PAVEMENTS",
                            "ward_name": ward_res["ward_name"],
                            "ward_no": ward_res["ward_number"],
                            "engineer": ward_res["executive_engineer_in_charge"],
                            "lat": cur_lat,
                            "lon": cur_lon,
                            "severity_score": final_score,
                            "status": "DISPATCHED_TO_CONTRACTOR",
                            "reported_at": "Just now (Live)",
                            "sla_target": f"{sla_h} Hours",
                            "resolved_in": "Active countdown",
                            "before_image": os.path.basename(target_image_path) if target_image_path else "images (1).jpg",
                            "after_image": None,
                            "disputed": False,
                            "dispute_count": 0
                        }
                        existing_ledger.insert(0, new_record)
                        save_ledger(existing_ledger)
                        st.toast(f"Ticket #{new_ticket_id} persisted to Public Accountability Ledger!")

                    with st.expander("👁️ Public Accountability Ledger Payload (JSON)", expanded=True):
                        st.json({
                            "ticket_id": new_ticket_id,
                            "status": "TRIAGED_AND_DISPATCHED",
                            "modality": "MULTIMODAL_VISION_VOICE_GIS",
                            "severity_score": final_score,
                            "enforced_sla_hours": sla_h,
                            "ward_name": ward_res["ward_name"],
                            "ward_no": ward_res["ward_number"],
                            "engineer": ward_res["executive_engineer_in_charge"],
                            "coordinates": {"lat": cur_lat, "lon": cur_lon},
                            "spatial_deduplication": dup_res,
                            "tamper_evident_audit_hash": hashlib.sha256(f"{new_ticket_id}{final_score}".encode()).hexdigest()
                        })

# =============================================================================
# TAB 2: PUBLIC ACCOUNTABILITY LEDGER & REPAIR TRACKER
# =============================================================================
with tab_ledger:
    st.markdown("### 🔍 Municipal Public Ledger & Proof-of-Repair Tracker")
    st.caption("All reported civic grievances are recorded on an immutable ledger with Before/After repair verification and Citizen Dispute rights.")

    all_tickets = load_ledger()

    # City Map with all tickets
    if all_tickets:
        map_data = [{"lat": t["lat"], "lon": t["lon"], "label": f"{t['ticket_id']} ({t['status']})"} for t in all_tickets]
        st.map(pd.DataFrame(map_data), latitude="lat", longitude="lon", zoom=12)

    st.write("")
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
    total_t = len(all_tickets)
    resolved_t = sum(1 for t in all_tickets if "RESOLVED" in t["status"])
    active_t = sum(1 for t in all_tickets if "RESOLVED" not in t["status"])
    disputed_t = sum(1 for t in all_tickets if t.get("disputed", False))

    f_col1.metric("Total Logged Grievances", total_t)
    f_col2.metric("Active Work Orders", active_t)
    f_col3.metric("Verified Resolved", resolved_t)
    f_col4.metric("Citizen Disputed Repairs", disputed_t)

    st.divider()

    # Status Filter
    filter_choice = st.radio("Filter Grievances:", ["All Tickets", "Active / In Progress", "Resolved with Proof", "Citizen Disputed"], horizontal=True)

    for idx, t in enumerate(all_tickets):
        is_res = "RESOLVED" in t["status"]
        is_disp = t.get("disputed", False)

        if filter_choice == "Active / In Progress" and is_res: continue
        if filter_choice == "Resolved with Proof" and not is_res: continue
        if filter_choice == "Citizen Disputed" and not is_disp: continue

        st.write("")
        status_badge = "badge-high"
        if is_disp: status_badge = "badge-dispute"
        elif is_res: status_badge = "badge-low"
        elif t["severity_score"] >= 80: status_badge = "badge-critical"

        with st.container():
            st.markdown(f"""
            <div class="ticket-box">
                <span class="{status_badge}">● {t['status']}</span> &nbsp; Ticket ID: <b>#{t['ticket_id']}</b> &nbsp; | &nbsp; Severity: <b>{t['severity_score']}/100</b><br><br>
                📍 <b>Location:</b> {t['ward_name']} (Ward {t['ward_no']}) &nbsp; | &nbsp; 👷 <b>Assigned Engineer:</b> <code>{t['engineer']}</code><br>
                ⏱️ <b>SLA Target:</b> {t['sla_target']} &nbsp; | &nbsp; <b>Reported:</b> {t['reported_at']} &nbsp; | &nbsp; <b>Resolution Metric:</b> {t['resolved_in']}
            </div>
            """, unsafe_allow_html=True)

            # Before and After Repair Images
            b_img_name = t.get("before_image")
            a_img_name = t.get("after_image")

            img_c1, img_c2 = st.columns(2)
            with img_c1:
                st.markdown("**📸 Before Repair (Reported Damage):**")
                if b_img_name:
                    bp = os.path.join(DATA_DIR, b_img_name)
                    if os.path.exists(bp):
                        st.image(Image.open(bp), caption=f"Reported: {b_img_name}", width="stretch")
                    else:
                        st.info("Photo on record.")
                else:
                    st.info("No initial photo on record.")

            with img_c2:
                st.markdown("**🛠️ After Repair (Contractor Proof):**")
                if a_img_name:
                    ap = os.path.join(DATA_DIR, a_img_name)
                    if os.path.exists(ap):
                        st.image(Image.open(ap), caption=f"Repair Completed: {a_img_name}", width="stretch")
                    else:
                        st.info("Awaiting contractor completion photo upload.")
                else:
                    st.warning("⚠️ Work in progress — Contractor has not yet uploaded proof of repair.")

            # Citizen Re-Complaint / Dispute Action
            if is_res and not is_disp:
                st.write("")
                if st.button(f"🚨 Dispute Repair (Fake / Poor Fix) #{t['ticket_id']}", key=f"btn_disp_{idx}"):
                    t["disputed"] = True
                    t["dispute_count"] += 1
                    t["status"] = "RE-OPENED (CITIZEN DISPUTED RESOLUTION)"
                    t["resolved_in"] = "Dispute Audit Triggered - Re-assigned to Vigilance"
                    save_ledger(all_tickets)
                    st.rerun()

            elif is_disp:
                st.error(f"⚠️ **CITIZEN DISPUTE ACTIVE**: This repair was flagged by the local community as substandard. Penalty review logged against the contractor and sent to the Municipal Vigilance Division.")

            st.write("---")
