
from pathlib import Path

import pytest

from src.extraction.pdf_extractor import (
    extract_pdf_pages,
    find_target_section,
    parse_hamburg_section,
    german_number_to_string,
)

PDF_PATH = Path("data/raw/hamburg_2026.pdf")


@pytest.fixture(scope="module")
def parsed_hamburg_data():
    """Extract and parse the official Hamburg report once."""

    if not PDF_PATH.exists():
        pytest.skip("Hamburg source PDF is not available.")

    pages = extract_pdf_pages(PDF_PATH)
    target_pages = find_target_section(pages)

    return parse_hamburg_section(target_pages)


def test_german_number_conversion():
    assert german_number_to_string("4,11") == "4.11"
    assert german_number_to_string("22.494") == "22494"
    assert german_number_to_string("2,26") == "2.26"


def test_target_section_contains_three_pages():
    pages = extract_pdf_pages(PDF_PATH)
    target_pages = find_target_section(pages)

    assert len(target_pages) == 3
    assert [page["page_number"] for page in target_pages] == [
        168, 169, 170
    ]


def test_base_rate_and_formula_coefficients(parsed_hamburg_data):
    metric = parsed_hamburg_data["metric"]

    assert metric["base_rate_percent"] == "4.11"
    assert metric["location_factor"]["exponent"] == "-1.4861"
    assert metric["rent_factor"]["exponent"] == "0.0948"
    assert metric["first_occupancy_factor"] == "0.84"


def test_update_factors(parsed_hamburg_data):
    factors = parsed_hamburg_data["dataset"]["update_factors"]

    assert len(factors) == 7

    assert factors[0]["valuation_date"] == "01.01.2023"
    assert factors[0]["value"] == "1.10"

    assert factors[-1]["valuation_date"] == "01.01.2026"
    assert factors[-1]["value"] == "1.10"


def test_sample_size_and_statistics(parsed_hamburg_data):
    dataset = parsed_hamburg_data["dataset"]

    assert dataset["selected_transactions"] == 110

    statistics = dataset["sample_statistics"]

    assert statistics["BRW22_EUR_per_m2"]["mean"] == "429"
    assert statistics["construction_year"]["mean"] == "1975"
    assert statistics["usable_area_m2"]["mean"] == "3548"
    assert statistics["net_cold_rent_EUR_per_m2"]["mean"] == "6.04"


def test_quality_indicator(parsed_hamburg_data):
    quality = parsed_hamburg_data["quality_metric"]

    assert quality["value_percent"] == "26"
