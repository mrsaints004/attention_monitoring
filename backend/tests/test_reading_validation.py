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
