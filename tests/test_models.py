
from decimal import Decimal

import pytest

from src.normalization.models import AppraisalMetric


def test_create_illustrative_metric():
    metric = AppraisalMetric(
        region="Bayern",
        asset_class="Logistics",
        metric_name="Liegenschaftszinssatz",
        reference_year=2025,
        value=Decimal("5.25"),
        unit="%",
        source_name="Illustrative test fixture",
        is_illustrative=True,
    )

    assert metric.region == "Bayern"
    assert metric.asset_class == "Logistics"
    assert metric.value == Decimal("5.25")
    assert metric.is_illustrative is True


def test_official_record_requires_source_url():
    with pytest.raises(ValueError):
        AppraisalMetric(
            region="Bayern",
            asset_class="Logistics",
            metric_name="Liegenschaftszinssatz",
            reference_year=2025,
            value=Decimal("5.25"),
            unit="%",
            source_name="Test report",
            is_illustrative=False,
        )


def test_invalid_year_is_rejected():
    with pytest.raises(ValueError):
        AppraisalMetric(
            region="Bayern",
            asset_class="Logistics",
            metric_name="Liegenschaftszinssatz",
            reference_year=1800,
            value=Decimal("5.25"),
            unit="%",
            source_name="Test fixture",
            is_illustrative=True,
        )


#------------------------------------------------------ 


from src.normalization.keys import generate_stable_key


def test_same_record_generates_same_key():
    metric = AppraisalMetric(
        region="Bayern",
        asset_class="Logistics",
        metric_name="Liegenschaftszinssatz",
        reference_year=2025,
        value=Decimal("5.25"),
        unit="%",
        source_name="Test fixture",
        is_illustrative=True,
    )

    first_key = generate_stable_key(metric)
    second_key = generate_stable_key(metric)

    assert first_key == second_key


def test_value_change_does_not_change_key():
    first_metric = AppraisalMetric(
        region="Bayern",
        asset_class="Logistics",
        metric_name="Liegenschaftszinssatz",
        reference_year=2025,
        value=Decimal("5.25"),
        unit="%",
        source_name="Test fixture",
        is_illustrative=True,
    )

    updated_metric = AppraisalMetric(
        region="Bayern",
        asset_class="Logistics",
        metric_name="Liegenschaftszinssatz",
        reference_year=2025,
        value=Decimal("5.50"),
        unit="%",
        source_name="Test fixture",
        is_illustrative=True,
    )

    assert (
        generate_stable_key(first_metric)
        == generate_stable_key(updated_metric)
    )
