
from pathlib import Path
import json
import re

import pymupdf


DEFAULT_PDF = Path("data/raw/hamburg_2026.pdf")
OUTPUT_JSON = Path("data/fixtures/hamburg_2026_parsed.json")


def extract_pdf_pages(pdf_path: Path = DEFAULT_PDF) -> list[dict]:
    """Extract text from every page of a PDF."""

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    extracted_pages = []

    with pymupdf.open(pdf_path) as document:
        for page_index, page in enumerate(document):
            extracted_pages.append({
                "page_number": page_index + 1,
                "text": page.get_text("text")
            })

    return extracted_pages


def find_target_section(pages: list[dict]) -> list[dict]:
    """Find the actual Hamburg logistics section 7.5.3."""

    for index, page in enumerate(pages):
        normalized_text = " ".join(
            page["text"].casefold().split()
        )

        is_target = (
            "7.5.3" in normalized_text
            and "produktions- und logistik-immobilien" in normalized_text
            and "sachlicher geltungsbereich" in normalized_text
        )

        if is_target:
            section_pages = pages[index:index + 3]

            if len(section_pages) != 3:
                raise ValueError(
                    "The target section does not contain all 3 expected pages."
                )

            return section_pages

    raise ValueError("Target section 7.5.3 was not found.")


def normalize_text(text: str) -> str:
    """Normalize whitespace without changing the original source."""

    return re.sub(r"\s+", " ", text).strip()


def german_number_to_string(value: str) -> str:
    """
    Convert German-formatted numbers into standard decimal strings.

    Examples:
        4,11   -> 4.11
        22.494 -> 22494
        2,26   -> 2.26
    """

    value = value.strip()

    if "," in value:
        return value.replace(".", "").replace(",", ".")

    return value.replace(".", "")


def extract_value(
    pattern: str,
    text: str,
    field_name: str
) -> str:
    """Extract one value using a regular expression."""

    match = re.search(pattern, text, flags=re.IGNORECASE)

    if not match:
        raise ValueError(
            f"Could not extract required field: {field_name}"
        )

    return german_number_to_string(match.group(1))


def parse_update_factors(text: str) -> list[dict]:
    """Extract the valuation update factors."""

    pattern = (
        r"(\d{1,2}\.\d{1,2}\.\d{4}\s+bis\s+"
        r"\d{1,2}\.\d{1,2}\.\d{4})\s+"
        r"(\d{2}\.\d{2}\.\d{4})\s+"
        r"([\d,]+)"
    )

    matches = re.findall(pattern, text)

    if len(matches) != 7:
        raise ValueError(
            f"Expected 7 update factors, found {len(matches)}"
        )

    factors = []

    for period, valuation_date, value in matches:
        factors.append({
            "investigation_period": period,
            "valuation_date": valuation_date,
            "value": german_number_to_string(value)
        })

    return factors


def parse_sample_statistics(text: str) -> dict:
    """Extract sample statistics from PDF page 170."""

    patterns = {
        "BRW22_EUR_per_m2": (
            r"BRW22\s*\[€/m²\]\s*"
            r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)"
        ),

        "construction_year": (
            r"Baujahr\s+"
            r"(\d{4})\s+(\d{4})\s+(\d{4})\s+(\d+)"
        ),

        "usable_area_m2": (
            r"Nutzfläche\s*\[m²\]\s*"
            r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)"
        ),

        "net_cold_rent_EUR_per_m2": (
            r"Nettokaltmiete\s*\[€/m²\]\s*"
            r"([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+(\d+)"
        )
    }

    statistics = {}

    for field_name, pattern in patterns.items():
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if not match:
            raise ValueError(
                f"Could not extract sample statistic: {field_name}"
            )

        values = match.groups()

        statistics[field_name] = {
            "minimum": german_number_to_string(values[0]),
            "maximum": german_number_to_string(values[1]),
            "mean": german_number_to_string(values[2]),
            "sample_size": int(values[3])
        }

    return statistics


def parse_hamburg_section(target_pages: list[dict]) -> dict:
    """Parse the Hamburg logistics appraisal section."""

    if len(target_pages) != 3:
        raise ValueError(
            f"Expected 3 section pages, received {len(target_pages)}"
        )

    page_168 = normalize_text(target_pages[0]["text"])
    page_169 = normalize_text(target_pages[1]["text"])
    page_170 = normalize_text(target_pages[2]["text"])

    # 1. Extract the base rate.
    base_rate = extract_value(
        r"=\s*([\d,]+)\s*\[%\]",
        page_168,
        "base_rate_percent"
    )

    # 2. Extract the location factor exponent.
    location_exponent = extract_value(
        r"\(BRW22\s*/\s*440\)\s*(-?[\d,]+)",
        page_168,
        "location_factor_exponent"
    )

    # 3. Extract the rent factor exponent.
    rent_exponent = extract_value(
        r"\(MM/RM\)\s*(-?[\d,]+)",
        page_168,
        "rent_factor_exponent"
    )

    # 4. Extract the first occupancy factor.
    # Important: anchor the search to the label followed by a colon.
    # This avoids matching the earlier formula occurrence.
    first_occupancy_factor = extract_value(
        r"Erstbezugsfaktor\s*:\s*für.*?\b(0,\d+)\b",
        page_168,
        "first_occupancy_factor"
    )

    # 5. Extract update factors.
    update_factors = parse_update_factors(page_169)

    # 6. Extract selected transaction count.
    sample_size_match = re.search(
        r"(\d+)\s+Kauffälle",
        page_169,
        flags=re.IGNORECASE
    )

    if not sample_size_match:
        raise ValueError("Sample size was not found.")

    sample_size = int(sample_size_match.group(1))

    # 7. Extract sample statistics.
    sample_statistics = parse_sample_statistics(page_170)

    # 8. Extract the quality indicator.
    quality_match = re.search(
        r"(?:±|\+/-)\s*([\d,]+)\s*%",
        page_170
    )

    if not quality_match:
        raise ValueError("Quality indicator was not found.")

    quality_value = german_number_to_string(
        quality_match.group(1)
    )

    return {
        "source": {
            "authority": "Gutachterausschuss für Grundstückswerte in Hamburg",
            "report_year": 2026,
            "printed_pages": [166, 167, 168],
            "pdf_pages": [168, 169, 170]
        },

        "metric": {
            "asset_class": "Production and Logistics Properties",
            "name": "Liegenschaftszinssatz",
            "base_rate_percent": base_rate,
            "unit": "%",
            "value_type": "base_rate",

            "formula": (
                "base_rate * location_factor * rent_factor "
                "* first_occupancy_factor * update_factor"
            ),

            "location_factor": {
                "base_land_value": "BRW22",
                "reference_value": "440",
                "exponent": location_exponent
            },

            "rent_factor": {
                "market_rent": "MM",
                "reference_rent": "RM",
                "exponent": rent_exponent
            },

            "first_occupancy_factor": first_occupancy_factor
        },

        "dataset": {
            "selected_transactions": sample_size,
            "selection_period": "2009-2021",
            "update_factors": update_factors,
            "sample_statistics": sample_statistics
        },

        "quality_metric": {
            "name": "relative_standard_deviation",
            "value_percent": quality_value
        },

        "limitations": [
            "The extracted base rate is not a final property-specific rate.",
            "The final rate requires the relevant adjustment factors.",
            "The report's selection criteria mention 2009-2021, "
            "while its transaction-year table displays years through 2025.",
            "The extracted data should be checked against the original PDF."
        ]
    }


def save_json(
    data: dict,
    output_path: Path = OUTPUT_JSON
) -> None:
    """Save parsed data as UTF-8 JSON."""

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=4
        )

    print(f"\nParsed data saved to: {output_path}")


def main():
    """Run the complete PDF extraction and parsing pipeline."""

    try:
        pages = extract_pdf_pages()

        print(f"PDF loaded successfully: {len(pages)} pages")

        target_pages = find_target_section(pages)

        print(
            f"Target section found: {len(target_pages)} pages"
        )

        parsed_data = parse_hamburg_section(target_pages)

        save_json(parsed_data)

        print("\nExtraction summary")
        print("------------------")

        print(
            "Base rate:",
            parsed_data["metric"]["base_rate_percent"],
            "%"
        )

        print(
            "Location exponent:",
            parsed_data["metric"]["location_factor"]["exponent"]
        )

        print(
            "Rent exponent:",
            parsed_data["metric"]["rent_factor"]["exponent"]
        )

        print(
            "First occupancy factor:",
            parsed_data["metric"]["first_occupancy_factor"]
        )

        print(
            "Update factors:",
            len(parsed_data["dataset"]["update_factors"])
        )

        print(
            "Sample size:",
            parsed_data["dataset"]["selected_transactions"]
        )

        print(
            "Quality indicator:",
            parsed_data["quality_metric"]["value_percent"],
            "%"
        )

    except (FileNotFoundError, ValueError) as error:
        print(f"Extraction error: {error}")

    except pymupdf.FileDataError as error:
        print(f"PDF reading error: {error}")

    except Exception as error:
        print(f"Unexpected error: {error}")


if __name__ == "__main__":
    main()
