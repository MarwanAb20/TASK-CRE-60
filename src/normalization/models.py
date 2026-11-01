
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class AppraisalMetric:
    """
    Standardized representation of an official real estate appraisal metric.
    """

    region: str
    asset_class: str
    metric_name: str
    reference_year: int
    value: Decimal
    unit: str
    source_name: str

    source_url: Optional[str] = None
    source_page: Optional[int] = None
    is_illustrative: bool = False
    notes: Optional[str] = None

    # Additional information from official reports
    statistic_type: str = "reported_value"
    transaction_period_start: Optional[int] = None
    transaction_period_end: Optional[int] = None
    sample_size: Optional[int] = None
    formula: Optional[str] = None
    geographic_scope: Optional[str] = None

    def __post_init__(self):
        required_fields = {
            "region": self.region,
            "asset_class": self.asset_class,
            "metric_name": self.metric_name,
            "unit": self.unit,
            "source_name": self.source_name,
            "statistic_type": self.statistic_type,
        }

        for field_name, field_value in required_fields.items():
            if not field_value or not field_value.strip():
                raise ValueError(f"{field_name} cannot be empty")

        if not 1900 <= self.reference_year <= 2100:
            raise ValueError("Invalid reference year")

        if not isinstance(self.value, Decimal):
            raise TypeError("value must be a Decimal")

        if not self.value.is_finite():
            raise ValueError("value must be a finite number")

        if not self.is_illustrative and not self.source_url:
            raise ValueError("Official records must include a source URL")

        if self.source_page is not None and self.source_page < 1:
            raise ValueError("source_page must be greater than zero")

        if self.sample_size is not None and self.sample_size <= 0:
            raise ValueError("sample_size must be greater than zero")

        if (
            self.transaction_period_start is not None
            and self.transaction_period_end is not None
            and self.transaction_period_start > self.transaction_period_end
        ):
            raise ValueError("Transaction period start cannot exceed end")
