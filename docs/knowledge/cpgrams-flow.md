# Skill Note: CPGRAMS Portal Flow, Channel Ladder & Assisted OTP Handshake

## Overview & Architecture
CPGRAMS (`pgportal.gov.in`) is the Government of India's unified grievance redressing portal for central ministries, departments, and linked state authorities.
Key characteristics:
1. **No Public REST API**: The public relies on interactive web forms, making an assisted autonomous agent the vital digital bridge.
2. **Citizen-in-the-Loop OTP Verification**: The portal sends an SMS OTP to verify the citizen's mobile number before submission. The agent **must always pause** and hand control to the citizen to enter the OTP and approve the final review. Never automate or bypass OTP or CAPTCHA.
3. **Official Registration Number**: Post-submission outputs a unique, trackable Registration Number (e.g., `MOHUA/E/2026/00123`) with an official ~21-day resolution target and a 30-day appeal window.

---

## 1. The Channel Ladder
Civic grievances route according to administrative jurisdiction:

| Tier | Channel | Applicability | Return Value | Notes |
|---|---|---|---|---|
| **A** | **CPGRAMS** (`pgportal.gov.in`) | Central ministries, national highways (NHAI), railways, postal, urban affairs | Registration Number + PDF | Trackable via "View Status"; 21-day resolution timeline; 30-day appeal window |
| **B** | **State / ULB Portals** (e.g. Karnataka Sahaaya / Spandana) | Municipal roads, ward streetlights, local sanitation | State Grievance ID | Direct jurisdiction over municipal issues; flaky APIs |
| **C** | **Swachhata App** (MoHUA) | Garbage dumps, public toilets, civic sanitation | Geo-tagged Complaint ID | Sanitation-specific |
| **D** | **Official Municipal Email** | Fallback when no portal exists | Email Message-ID | **Untracked**. Must be displayed transparently as "Filed — awaiting acknowledgment" |

---

## 2. Patterns
- **Human-in-the-Loop Checkpoint**: The agent runs the browser until encountering the OTP/CAPTCHA step, transitions status to `awaiting_human`, and notifies the citizen via the UI/SMS sidecar. Once the citizen types the OTP, the agent resumes execution.
- **Registration Number Scraping**: Look for standard regex patterns on the confirmation page:
  `[A-Z]{3,8}/[A-Z]/202[4-9]/\d{4,8}`
- **Automated Evidence Capture**: After submission, trigger `page.pdf()` or take full-page screenshot as cryptographic evidence for the audit ledger.

---

## 3. Common Pitfalls
1. **Routing State Issues to Central CPGRAMS**: CPGRAMS central ministries will immediately reject or transfer municipal road/pothole issues with an administrative delay. State issues must route to State/ULB channels.
2. **Automating Bot Checks (Anti-Pattern)**: Trying to OCR CAPTCHAs or automate OTP violates portal terms of service and hackathon safety rules. Let the human handle OTP/CAPTCHA, let the AI handle form-filling.
3. **Missing Appeal Deadlines**: If a portal marks a ticket "Closed/Resolved" but the issue remains unresolved, CPGRAMS only permits appeal within 30 days of closure.

---

## 4. Minimal Working Code Skeleton

```python
import re
from playwright.async_api import Page

REG_NO_PATTERN = re.compile(r"([A-Z0-9]{3,8}/[A-Z0-9]/202\d/\d{5,8})")

async def extract_cpgrams_confirmation(page: Page) -> dict:
    """Extracts registration number and confirmation status from portal confirmation page."""
    body_text = await page.inner_text("main, body")
    match = REG_NO_PATTERN.search(body_text)
    
    reg_no = match.group(1) if match else None
    success = "successfully registered" in body_text.lower() or reg_no is not None
    
    evidence_png = await page.screenshot(full_page=True)
    return {
        "success": success,
        "registration_number": reg_no,
        "status_url": f"https://pgportal.gov.in/Status/Index?reg={reg_no}" if reg_no else None,
        "evidence_bytes": evidence_png
    }
```

---

## 5. Verified Source Links
- CPGRAMS Official Portal: https://pgportal.gov.in/
- Ministry of Personnel, Public Grievances and Pensions Guidelines: https://darpg.gov.in/
- IT Act 2000 §43 & §66 Compliance Principles: https://www.meity.gov.in/content/information-technology-act-2000
