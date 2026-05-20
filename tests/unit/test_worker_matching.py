"""Unit tests for worker matching distance calculation."""

from decimal import Decimal

from app.services.worker_matching import _haversine_km


def test_same_point_is_zero():
    lat, lon = Decimal("51.5074"), Decimal("-0.1278")
    assert _haversine_km(lat, lon, lat, lon) == 0.0


def test_london_to_manchester_approx():
    # London to Manchester is ~263 km
    london_lat, london_lon = Decimal("51.5074"), Decimal("-0.1278")
    manc_lat, manc_lon = Decimal("53.4808"), Decimal("-2.2426")
    dist = _haversine_km(london_lat, london_lon, manc_lat, manc_lon)
    assert 250 < dist < 275


def test_short_distance_within_same_city():
    # Two points ~5 km apart in London
    point_a = (Decimal("51.5074"), Decimal("-0.1278"))
    point_b = (Decimal("51.5500"), Decimal("-0.1000"))
    dist = _haversine_km(*point_a, *point_b)
    assert dist < 10


def test_distance_is_symmetric():
    lat1, lon1 = Decimal("51.5074"), Decimal("-0.1278")
    lat2, lon2 = Decimal("53.4808"), Decimal("-2.2426")
    assert abs(_haversine_km(lat1, lon1, lat2, lon2) - _haversine_km(lat2, lon2, lat1, lon1)) < 0.001
