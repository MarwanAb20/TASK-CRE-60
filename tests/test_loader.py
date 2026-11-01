
import json
from decimal import Decimal
from pathlib import Path
from datetime import date
from decimal import Decimal

import pytest

from src.normalization.loader import load_metric_fixture


FIXTURE_PATH = Path("data/fixtures/hamburg_2026_logistics.json")


def test_load_hamburg_fixture():
    metric, original_data = load_metric_fixture(FIXTURE_PATH)

    assert metric.region == "Hamburg"
    assert metric.metric_name == "Liegenschaftszinssatz"
    assert metric.value == Decimal("4.11")
    assert metric.statistic_type == "base_rate"
    assert metric.transaction_period_start == 2009
    assert metric.transaction_period_end == 2021
    assert metric.sample_size == 110

    # The original adjustment factors must remain available.
    assert len(original_data["metric"]["factors"]) == 3


def test_loader_rejects_missing_section(tmp_path):
    incomplete_data = {
        "source": {},
        "metric": {}
    }

    fixture_path = tmp_path / "incomplete.json"
    fixture_path.write_text(
        json.dumps(incomplete_data),
        encoding="utf-8"
    )

    with pytest.raises(ValueError, match="Missing section"):
        load_metric_fixture(fixture_path)


def test_loader_rejects_invalid_json(tmp_path):
    fixture_path = tmp_path / "invalid.json"
    fixture_path.write_text("{invalid json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        load_metric_fixture(fixture_path)

def test_hamburg_update_factors():
    _, original_data = load_metric_fixture(FIXTURE_PATH)

    update_factors = original_data["metric"]["update_factors"]

    assert len(update_factors) == 7

    for factor in update_factors:
        date.fromisoformat(factor["valuation_date"])
        assert Decimal(factor["value"]) > 0

    assert update_factors[0]["valuation_date"] == "2023-01-01"
    assert Decimal(update_factors[0]["value"]) == Decimal("1.10")

    assert update_factors[-1]["valuation_date"] == "2026-01-01"
    assert Decimal(update_factors[-1]["value"]) == Decimal("1.10")
