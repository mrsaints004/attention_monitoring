import pytest
from app.auth import instructor_token


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_create_session(client):
    r = await client.post("/api/sessions", json={
        "instructor_name": "Dr. Smith",
        "instructor_email": "smith@test.com",
        "course_name": "CS101",
    })
    assert r.status_code == 200
    data = r.json()
    assert "session_id" in data
    assert len(data["join_code"]) == 6


@pytest.mark.asyncio
async def test_get_session(client):
    r = await client.post("/api/sessions", json={
        "instructor_name": "Dr. Smith",
        "instructor_email": "smith2@test.com",
        "course_name": "CS102",
    })
    sid = r.json()["session_id"]

    r = await client.get(f"/api/sessions/{sid}", headers={"Authorization": "Bearer " + instructor_token(sid)})
    assert r.status_code == 200
    data = r.json()
    assert data["course_name"] == "CS102"
    assert data["instructor_name"] == "Dr. Smith"
    assert len(data["students"]) == 0


@pytest.mark.asyncio
async def test_join_session(client):
    r = await client.post("/api/sessions", json={
        "instructor_name": "Dr. Smith",
        "instructor_email": "smith3@test.com",
        "course_name": "CS103",
    })
    sid = r.json()["session_id"]

    r = await client.post(f"/api/sessions/{sid}/join", json={
        "consent_version": "v1", "display_name": "Alice",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["student_id"]
    assert data["device_token"]

    # Verify student appears in session
    r = await client.get(f"/api/sessions/{sid}", headers={"Authorization": "Bearer " + instructor_token(sid)})
    assert len(r.json()["students"]) == 1
    assert r.json()["students"][0]["display_name"] == "Alice"


@pytest.mark.asyncio
async def test_join_with_device_token_upserts(client):
    r = await client.post("/api/sessions", json={
        "instructor_name": "Dr. Smith",
        "instructor_email": "smith4@test.com",
        "course_name": "CS104",
    })
    sid = r.json()["session_id"]

    r = await client.post(f"/api/sessions/{sid}/join", json={
        "consent_version": "v1", "display_name": "Bob",
    })
    token = r.json()["device_token"]
    student_id = r.json()["student_id"]

    # Rejoin with same device token updates display name
    r = await client.post(f"/api/sessions/{sid}/join", json={
        "consent_version": "v1", "display_name": "Bobby",
        "device_token": token,
    })
    assert r.json()["student_id"] == student_id
    assert r.json()["device_token"] == token


@pytest.mark.asyncio
async def test_end_session(client):
    r = await client.post("/api/sessions", json={
        "instructor_name": "Dr. Smith",
        "instructor_email": "smith5@test.com",
        "course_name": "CS105",
    })
    sid = r.json()["session_id"]

    r = await client.post(f"/api/sessions/{sid}/end", headers={"Authorization": "Bearer " + instructor_token(sid)})
    assert r.status_code == 200
    assert r.json()["status"] == "ended"

    # Can't join ended session
    r = await client.post(f"/api/sessions/{sid}/join", json={
        "consent_version": "v1", "display_name": "Late Student",
    })
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_get_session_by_code(client):
    r = await client.post("/api/sessions", json={
        "instructor_name": "Dr. Smith",
        "instructor_email": "smith6@test.com",
        "course_name": "CS106",
    })
    code = r.json()["join_code"]

    r = await client.get(f"/api/sessions/code/{code}")
    assert r.status_code == 200
    assert r.json()["course_name"] == "CS106"


@pytest.mark.asyncio
async def test_session_not_found(client):
    r = await client.get("/api/sessions/nonexistent-id")
    assert r.status_code == 404
