import pytest

from ilovestock.eta import estimate_eta


@pytest.mark.parametrize(
    ("phase_started", "now", "done", "total", "expected"),
    [
        (10.0, 20.0, 2, 0, None),
        (10.0, 20.0, 0, 10, None),
        (10.0, 20.0, 1, 10, None),
        (10.0, 20.0, 5, 10, 10.0),
        (10.0, 20.0, 10, 10, 0.0),
        (10.0, 20.0, 11, 10, 0.0),
        (10.0, 20.0, 2, -1, None),
        (None, 20.0, 2, 10, None),
        (20.0, 10.0, 2, 10, 0.0),
    ],
)
def test_estimate_eta(phase_started, now, done, total, expected):
    assert estimate_eta(phase_started, now, done, total) == expected
