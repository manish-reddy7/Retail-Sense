from datetime import date
import pytest
from src.data.leakage_audit import assert_no_future_features


def test_future_feature_is_rejected():
    with pytest.raises(ValueError):
        assert_no_future_features(date(2026, 1, 2), {"lag_1": date(2026, 1, 2)})


def test_past_feature_is_accepted():
    assert_no_future_features(date(2026, 1, 2), {"lag_1": date(2026, 1, 1)})

