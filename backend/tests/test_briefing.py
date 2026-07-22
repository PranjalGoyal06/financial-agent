import pytest
from datetime import datetime, timezone, timedelta
from app.briefing.service import _get_relative_time_string, _get_vix_tier, _get_market_closed_time

def test_get_relative_time_string():
    now = datetime.now(timezone.utc)
    assert _get_relative_time_string(now) == "just now"
    assert _get_relative_time_string(now - timedelta(seconds=30)) == "just now"
    assert _get_relative_time_string(now - timedelta(minutes=5)) == "5 min ago"
    assert _get_relative_time_string(now - timedelta(minutes=59)) == "59 min ago"
    assert _get_relative_time_string(now - timedelta(hours=2)) == "2 hours ago"
    assert _get_relative_time_string(now - timedelta(hours=1)) == "1 hour ago"
    assert _get_relative_time_string(now - timedelta(days=1)) == "1 day ago"
    assert _get_relative_time_string(now - timedelta(days=3)) == "3 days ago"


def test_get_vix_tier():
    assert _get_vix_tier(12.0) == "low"
    assert _get_vix_tier(14.9) == "low"
    assert _get_vix_tier(15.0) == "moderate"
    assert _get_vix_tier(19.9) == "moderate"
    assert _get_vix_tier(20.0) == "elevated"
    assert _get_vix_tier(29.9) == "elevated"
    assert _get_vix_tier(30.0) == "high"
    assert _get_vix_tier(45.0) == "high"
