"""The pressure model tracks SILCA's calculator.

Reference points read off SILCA's pro tire pressure calculator: system weight =
rider + 25 lb, gravel 47/53 front/rear split, high-performance tubeless casing,
17.5 mph. Keyed (rider_lb, width_mm, gravel category) -> (front, rear) psi.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))
from generate_tire_guide import BIKE_AND_KIT_LB, pressure_psi  # noqa: E402

TOLERANCE_PSI = 0.6

SILCA = {
    (150, 40, 2): (36.9, 38.6),
    (150, 45, 2): (30.3, 31.7),
    (150, 50, 3): (22.2, 23.2),
    (170, 45, 1): (34.0, 35.5),
    (170, 50, 4): (20.9, 21.8),
    (190, 40, 3): (34.2, 35.8),
    (190, 45, 4): (25.8, 27.0),
    (190, 50, 2): (26.0, 27.2),
}


def test_system_weight_is_rider_plus_25_lb():
    assert BIKE_AND_KIT_LB == 25


@pytest.mark.parametrize("key", sorted(SILCA), ids=[f"{r}lb-{w}mm-cat{c}" for r, w, c in sorted(SILCA)])
def test_matches_silca(key):
    rider, width, cat = key
    want_front, want_rear = SILCA[key]
    front, rear = pressure_psi(rider, width, cat)
    assert abs(front - want_front) <= TOLERANCE_PSI, (key, round(front, 2), want_front)
    assert abs(rear - want_rear) <= TOLERANCE_PSI, (key, round(rear, 2), want_rear)


def test_rear_runs_higher_than_front():
    for rider, width, cat in SILCA:
        front, rear = pressure_psi(rider, width, cat)
        assert rear > front
