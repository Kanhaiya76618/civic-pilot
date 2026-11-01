"""Evidence delivery: the bucket stays private, the server serves files, citizens' own files need the municipal desk."""

import pytest
from fastapi.testclient import TestClient

from server import storage
from server.storage import EVIDENCE_PREFIX, storage_path_of


def test_storage_paths_from_references_and_old_links(monkeypatch):
    monkeypatch.setattr(storage, "SUPABASE_URL", "https://abc.supabase.co")
    monkeypatch.setattr(storage, "SUPABASE_BUCKET", "evidence")
    assert storage_path_of(EVIDENCE_PREFIX + "r1/f.png") == "r1/f.png"
    assert storage_path_of("https://abc.supabase.co/storage/v1/object/public/evidence/r1/f.png") == "r1/f.png"  # old rows
    assert storage_path_of("https://abc.supabase.co/storage/v1/object/sign/evidence/r1/f.png?token=x") == "r1/f.png"
    assert storage_path_of("https://images.unsplash.com/photo-1?w=800") is None  # outside links are not our evidence
    assert storage_path_of("https://evil.example/storage/v1/object/public/evidence/r1/f.png") is None
    assert storage_path_of(EVIDENCE_PREFIX + "../secrets/x") is None and storage_path_of(EVIDENCE_PREFIX + "a/b/c") is None
    assert storage_path_of(None) is None


def test_voice_notes_are_accepted_with_their_real_type():
    assert storage.validate_file(b"x" * 10, "voice.webm", "audio/webm") == ".webm"
    with pytest.raises(storage.StorageValidationError):
        storage.validate_file(b"x" * 10, "voice.webm", "application/pdf")  # the old upload path, always rejected


@pytest.fixture(scope="module")
def client():
    from executor.api import make_app
    with TestClient(make_app()) as c:
        yield c


def test_public_board_never_exposes_raw_storage_links(client):
    reports = client.get("/api/public/reports").json()
    for r in reports:
        assert r["evidence_urls"] == []  # citizens' photos are not public
        assert r["resolution_proof_url"] is None or r["resolution_proof_url"].startswith("/api/v1/evidence/")


def test_proof_is_public_but_citizen_evidence_needs_the_desk(client):
    resolved = [r for r in client.get("/api/public/reports").json() if r["resolution_proof_url"]]
    if not resolved:
        pytest.skip("no resolved report with stored proof in this database")
    client.cookies.clear()
    proof = client.get(resolved[0]["resolution_proof_url"])
    assert proof.status_code == 200 and proof.headers["content-type"].startswith("image/") and len(proof.content) > 100
    assert client.get(f"/api/v1/evidence/{resolved[0]['id']}/0").status_code == 401  # signed out: no citizen files
    assert client.get("/api/v1/evidence/not-a-report/proof").status_code == 404
