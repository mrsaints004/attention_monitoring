import pytest
from pydantic import ValidationError
from app.schemas.reading import ReadingIn


@pytest.mark.parametrize("field,value", [
    ("s_eye", -0.1), ("s_gaze", 1.1), ("s_yawn", float("nan")),
    ("s_affect", float("inf")), ("attention_index", -1),
    ("attention_index", 101), ("quality_flag", "unknown"),
])
def test_rejects_invalid_readings(field, value):
    payload = dict(s_eye=1, s_gaze=1, s_yawn=1, s_affect=1, attention_index=100)
    payload[field] = value
    with pytest.raises(ValidationError):
        ReadingIn(**payload)


def test_accepts_valid_reading():
    reading = ReadingIn(s_eye=0, s_gaze=0.5, s_yawn=1, s_affect=0.7, attention_index=55)
    assert reading.quality_flag.value == "normal"


def test_geometric_mode_does_not_claim_affect_details():
    reading = ReadingIn(s_eye=1, s_gaze=1, s_yawn=1, s_affect=0.5, attention_index=90,
                        boredom=0.8, confusion=0.2, inference_mode="geometric")
    assert reading.boredom is None and reading.confusion is None


def test_affect_details_require_valid_ranges_and_reliable_images():
    payload = dict(s_eye=1, s_gaze=1, s_yawn=1, s_affect=0.7, attention_index=90,
                   inference_mode="four_cue", boredom=0.2, confusion=0.3)
    reading = ReadingIn(**payload)
    assert reading.boredom == 0.2 and reading.confusion == 0.3
    with pytest.raises(ValidationError):
        ReadingIn(**{**payload, "boredom": float("nan")})
    paused = ReadingIn(**{**payload, "quality_flag": "monitoring_paused"})
    assert paused.boredom is None and paused.confusion is None and paused.attention_index is None
