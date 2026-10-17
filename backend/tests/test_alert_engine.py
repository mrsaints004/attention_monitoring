import pytest
import time
from unittest.mock import AsyncMock, MagicMock

from app.services.alert_engine import AlertEngine


class FakeDB:
    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def flush(self):
        pass


@pytest.mark.asyncio
async def test_no_alert_when_above_threshold():
    engine = AlertEngine()
    db = FakeDB()
    alerts = await engine.process_reading(db, "s1", "r1", 80, "normal", 0.5)
    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_no_alert_before_duration():
    engine = AlertEngine()
    db = FakeDB()
    # First reading below threshold - starts timer
    alerts = await engine.process_reading(db, "s1", "r1", 30, "normal", 0.5)
    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_alert_fires_after_duration():
    engine = AlertEngine()
    db = FakeDB()

    # Simulate time passing by manipulating state
    state = engine._get_state("s1")
    state.low_attention_since = time.time() - 20  # 20 seconds ago

    alerts = await engine.process_reading(db, "s1", "r1", 30, "normal", 0.5)
    assert len(alerts) == 1
    assert alerts[0].alert_type.value == "low_attention"


@pytest.mark.asyncio
async def test_cooldown_prevents_spam():
    engine = AlertEngine()
    db = FakeDB()

    state = engine._get_state("s1")
    state.low_attention_since = time.time() - 20
    alerts = await engine.process_reading(db, "s1", "r1", 30, "normal", 0.5)
    assert len(alerts) == 1

    # Immediately another low reading should be suppressed by cooldown
    state.low_attention_since = time.time() - 20
    db2 = FakeDB()
    alerts = await engine.process_reading(db2, "s1", "r2", 30, "normal", 0.5)
    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_eyes_closed_alert():
    engine = AlertEngine()
    db = FakeDB()

    state = engine._get_state("s1")
    state.eyes_closed_since = time.time() - 5  # 5 seconds ago

    alerts = await engine.process_reading(db, "s1", "r1", 80, "normal", 0.05)
    assert any(a.alert_type.value == "eyes_closed" for a in alerts)


@pytest.mark.asyncio
async def test_face_not_detected_alert():
    engine = AlertEngine()
    db = FakeDB()

    state = engine._get_state("s1")
    state.face_missing_since = time.time() - 20

    alerts = await engine.process_reading(db, "s1", "r1", 0, "face_not_detected", 0)
    assert any(a.alert_type.value == "face_not_detected" for a in alerts)


@pytest.mark.asyncio
async def test_remove_student():
    engine = AlertEngine()
    engine._get_state("s1")
    assert "s1" in engine.states
    engine.remove_student("s1")
    assert "s1" not in engine.states


@pytest.mark.asyncio
@pytest.mark.parametrize("flag", ["low_confidence", "monitoring_paused", "away", "tab_inactive", "face_not_detected"])
async def test_unreliable_readings_never_trigger_attention_alerts(flag):
    engine = AlertEngine()
    state = engine._get_state("s1")
    state.low_attention_since = time.time() - 30
    state.eyes_closed_since = time.time() - 30
    alerts = await engine.process_reading(FakeDB(), "s1", "r1", 0, flag, 0)
    assert not alerts
    assert state.low_attention_since is None
    assert state.eyes_closed_since is None


@pytest.mark.asyncio
async def test_recovery_during_cooldown_resets_episode():
    engine = AlertEngine()
    state = engine._get_state("s1")
    state.last_alert_time = time.time()
    state.low_attention_since = time.time() - 30
    state.eyes_closed_since = time.time() - 30
    await engine.process_reading(FakeDB(), "s1", "r1", 90, "normal", 1)
    assert state.low_attention_since is None
    assert state.eyes_closed_since is None
