
import hashlib
import json

from src.normalization.models import AppraisalMetric


def generate_stable_key(metric: AppraisalMetric) -> str:
    """
    Generate a deterministic identifier for an appraisal record.

    The metric value is intentionally excluded so that an updated
    value for the same source observation keeps the same key.
    """

    identity = {
        "region": metric.region.strip().casefold(),
        "asset_class": metric.asset_class.strip().casefold(),
        "metric_name": metric.metric_name.strip().casefold(),
        "reference_year": metric.reference_year,
        "unit": metric.unit.strip().casefold(),
        "source_name": metric.source_name.strip().casefold(),
        "source_url": (
            metric.source_url.strip()
            if metric.source_url else None
        ),
        "source_page": metric.source_page,
    }

    canonical_data = json.dumps(
        identity,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonical_data.encode("utf-8")
    ).hexdigest()
