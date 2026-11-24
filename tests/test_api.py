"""API tests, including one full run on a generated video (upload, split, edit, export, zip)."""

import time
import zipfile

import cv2
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(work_dir):
    from app.main import app  # imported here so CLIPPER_WORK_DIR is already set

    with TestClient(app) as test_client:
        yield test_client


def wait_for_job(client, job_id, timeout=300):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.5)
    raise AssertionError("job did not finish in time")


def test_health_and_index(client):
    assert client.get("/api/health").json()["ok"] is True
    assert client.get("/").status_code == 200


@pytest.mark.parametrize("url", [
    "http://example.com/video",
    "https://evil.example.org/watch?v=abc",
    "javascript:alert(1)",
    "file:///C:/Windows/win.ini",
])
def test_non_youtube_urls_are_rejected(client, url):
    response = client.post("/api/videos/from-url", json={"url": url})
    assert response.status_code == 400


def test_upload_with_wrong_extension_is_rejected(client):
    response = client.post("/api/videos/upload", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 400


def test_garbage_file_with_video_extension_fails_cleanly(client):
    response = client.post("/api/videos/upload", files={"file": ("fake.mp4", b"not a video" * 100, "video/mp4")})
    assert response.status_code == 202
    body = response.json()
    job = wait_for_job(client, body["job_id"])
    assert job["status"] == "error"
    assert "video" in job["error"].lower()
    assert client.get(f"/api/videos/{body['video_id']}").json()["status"] == "error"


def test_bad_ids_return_404(client):
    assert client.get("/api/videos/../../etc").status_code in (404, 405)
    assert client.get("/api/videos/not-a-real-id").status_code == 404
    assert client.get("/api/jobs/zzz").status_code == 404


def test_full_flow_upload_edit_export(client, sample_video):
    with open(sample_video, "rb") as handle:
        response = client.post("/api/videos/upload", files={"file": ("My Talk.mp4", handle, "video/mp4")})
    assert response.status_code == 202
    video_id = response.json()["video_id"]

    job = wait_for_job(client, response.json()["job_id"])
    assert job["status"] == "done", job
    video = client.get(f"/api/videos/{video_id}").json()
    assert video["status"] == "ready"
    assert (video["width"], video["height"]) == (1280, 720)
    assert video["title"] == "My Talk"
    assert len(video["clips"]) >= 1

    clip = video["clips"][0]

    # Trimming: out-of-range and too-short values are refused.
    assert client.patch(f"/api/videos/{video_id}/clips/{clip['id']}", json={"start": -1, "end": 5}).status_code == 400
    assert client.patch(f"/api/videos/{video_id}/clips/{clip['id']}", json={"start": 0, "end": 999}).status_code == 400
    assert client.patch(f"/api/videos/{video_id}/clips/{clip['id']}", json={"start": 4, "end": 4.2}).status_code == 400

    # Extending a clip past its automatic end is allowed, as long as it stays inside the video.
    edited = client.patch(f"/api/videos/{video_id}/clips/{clip['id']}", json={"start": 0.0, "end": 9.0}).json()
    edited_clip = next(c for c in edited["clips"] if c["id"] == clip["id"])
    assert (edited_clip["start"], edited_clip["end"]) == (0.0, 9.0)

    # Export one clip and check the result.
    job_id = client.post(f"/api/videos/{video_id}/clips/{clip['id']}/export").json()["job_id"]
    job = wait_for_job(client, job_id)
    assert job["status"] == "done", job
    download = client.get(f"/api/videos/{video_id}/clips/{clip['id']}/download")
    assert download.status_code == 200
    exported = download.content
    assert len(exported) > 1000

    capture_path = _write_bytes(exported)
    cap = cv2.VideoCapture(capture_path)
    assert int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) == 1080
    assert int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) == 1920
    cap.release()

    # Export all clips as one zip file.
    job_id = client.post(f"/api/videos/{video_id}/export-all").json()["job_id"]
    job = wait_for_job(client, job_id)
    assert job["status"] == "done", job
    bundle = client.get(f"/api/videos/{video_id}/bundle")
    assert bundle.status_code == 200
    names = zipfile.ZipFile(_write_bytes(bundle.content, suffix=".zip")).namelist()
    assert "clip-01.mp4" in names


def _write_bytes(data: bytes, suffix: str = ".mp4") -> str:
    import tempfile

    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    handle.write(data)
    handle.close()
    return handle.name
