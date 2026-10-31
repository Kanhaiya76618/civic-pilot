"""Seed synthetic personas, consents, vault entries and sample documents.

Used by the tests, the eval runner and the demo script. Synthetic data only.
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw

from executor.config import ROOT, settings
from executor.models import ApplicationTask, ConsentRecord, DocumentRef, TaskMode

PERSONAS = json.loads((ROOT / "tests" / "fixtures" / "personas.json").read_text())["personas"]


def _sample_certificate(path: Path, name: str) -> None:
    """A4-ish scan, ~300-600 KB as JPEG, so document prep has to shrink it."""
    img = Image.new("RGB", (1654, 2339), (250, 248, 240))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 60, 1594, 2279], outline=(40, 40, 40), width=6)
    d.text((200, 200), "SAMPLE INCOME CERTIFICATE (TEST FIXTURE, NOT A REAL DOCUMENT)", fill=(20, 20, 20))
    d.text((200, 300), f"Certified that the annual family income of {name} is below the scheme limit.", fill=(20, 20, 20))
    rnd = random.Random(7)
    for y in range(420, 2200, 28):
        d.line([(200, y), (200 + rnd.randint(600, 1250), y)], fill=(rnd.randint(60, 120),) * 3, width=3)
    for _ in range(40000):
        x, y = rnd.randint(0, 1653), rnd.randint(0, 2338)
        img.putpixel((x, y), (rnd.randint(150, 255),) * 3)
    img.save(path, "JPEG", quality=95)


def _sample_photo(path: Path) -> None:
    """A large 'photo' (~200 KB+) that must be cut to the portal's 50 KB / 600 px limit."""
    rnd = random.Random(11)
    img = Image.new("RGB", (1800, 2400), (180, 200, 220))
    d = ImageDraw.Draw(img)
    d.ellipse([500, 400, 1300, 1300], fill=(205, 160, 130))
    d.rectangle([350, 1300, 1450, 2400], fill=(40, 70, 120))
    for _ in range(30000):
        x, y = rnd.randint(0, 1799), rnd.randint(0, 2399)
        img.putpixel((x, y), (rnd.randint(0, 255), rnd.randint(0, 255), rnd.randint(0, 255)))
    img.save(path, "JPEG", quality=95)


def add_document(store, path: Path, media_type: str = "image/jpeg") -> str:
    doc_id = uuid.uuid4().hex[:16]
    dest = settings.uploads_dir / f"{doc_id}{path.suffix}"
    dest.write_bytes(path.read_bytes())
    store.put_document(doc_id, str(dest), media_type)
    return f"doc://{doc_id}"


def sample_docs(store, name: str) -> dict[str, str]:
    settings.ensure_dirs()
    tmp = settings.data_dir / "samples"
    tmp.mkdir(exist_ok=True)
    cert, photo = tmp / "income_certificate.jpg", tmp / "photo.jpg"
    if not cert.exists():
        _sample_certificate(cert, name)
    if not photo.exists():
        _sample_photo(photo)
    return {"income_certificate": add_document(store, cert), "photo": add_document(store, photo)}


def seed_task(
    executor,
    persona: int = 0,
    service: str = "scholarship_postmatric",
    mode: TaskMode = TaskMode.assist,
    vault_override: dict | None = None,
    with_attachment: bool = False,
    origin_ref: str | None = None,
) -> ApplicationTask:
    p = PERSONAS[persona]
    profile = p["profile"]
    executor.store.put_profile(profile)
    consent = ConsentRecord(
        consent_id="cons_" + uuid.uuid4().hex[:12],
        citizen_id=profile["citizen_id"],
        portal_ids=["sandbox"],
        service_ids=[service],
        purpose=f"File {service} on the citizen's behalf, with approval before submit",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    executor.store.put_consent(consent.model_dump(mode="json"))
    vault_ref = executor.vault.put(vault_override or p["vault"])
    docs: list[DocumentRef] = []
    if service == "scholarship_postmatric":
        docs = [DocumentRef(key=k, uri=v, media_type="image/jpeg") for k, v in sample_docs(executor.store, p["inputs"][service]["full_name"]).items()]
    elif with_attachment:
        docs = [DocumentRef(key="attachment", uri=sample_docs(executor.store, "x")["photo"], media_type="image/jpeg")]
    return ApplicationTask(
        idempotency_key="idem_" + uuid.uuid4().hex,
        citizen_id=profile["citizen_id"],
        portal_id="sandbox",
        service_id=service,
        inputs=dict(p["inputs"][service]),
        documents=docs,
        vault_ref=vault_ref,
        consent_id=consent.consent_id,
        mode=mode,
        origin="eval",
        origin_ref=origin_ref,
    )
