
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.normalization.models import AppraisalMetric


DEFAULT_FIXTURE = Path("data/fixtures/hamburg_2026_logistics.json")


def load_metric_fixture(
    path: Path = DEFAULT_FIXTURE,
) -> tuple[AppraisalMetric, dict[str, Any]]:
    """
    Load an official source fixture and convert its main metric
    into an AppraisalMetric object.

    The original JSON is also returned so that detailed factors
    and source metadata are not lost.
    """

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    # Check that the expected sections exist.
    for section in ("source", "metric", "dataset"):
        if section not in data:
            raise ValueError(f"Missing section in fixture: {section}")

    source = data["source"]
    metric_data = data["metric"]
    dataset = data["dataset"]

    transaction_years = dataset.get("transaction_years", [])

    if len(transaction_years) != 2:
        raise ValueError("transaction_years must contain start and end years")

    printed_pages = source.get("printed_pages", [])

    metric = AppraisalMetric(
        region="Hamburg",
        asset_class=metric_data["asset_class"],
        metric_name=metric_data["name"],
        reference_year=source["report_year"],
        value=Decimal(metric_data["base_rate_percent"]),
        unit=metric_data["unit"],
        source_name=source["authority"],
        source_url=source["url"],
        source_page=printed_pages[0] if printed_pages else None,
        is_illustrative=data.get("is_illustrative", False),
        notes="; ".join(data.get("limitations", [])),
        statistic_type=metric_data["value_type"],
        transaction_period_start=transaction_years[0],
        transaction_period_end=transaction_years[1],
        sample_size=dataset.get("selected_transactions"),
        formula=metric_data.get("formula"),
        geographic_scope=metric_data.get("geographic_scope"),
    )

    return metric, data


if __name__ == "__main__":
    appraisal_metric, original_data = load_metric_fixture()

    print("Fixture loaded successfully!")
    print("--------------------------------")
    print("Metric:", appraisal_metric.metric_name)
    print("Region:", appraisal_metric.region)
    print("Asset class:", appraisal_metric.asset_class)
    print("Value:", appraisal_metric.value, appraisal_metric.unit)
    print("Type:", appraisal_metric.statistic_type)
    print("Transaction period:",
          appraisal_metric.transaction_period_start,
          "-",
          appraisal_metric.transaction_period_end)
    print("Sample size:", appraisal_metric.sample_size)
    print("Source:", appraisal_metric.source_name)
    print("Adjustment factors:",
          len(original_data["metric"].get("factors", {})))
