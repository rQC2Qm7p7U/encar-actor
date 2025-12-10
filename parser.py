#!/usr/bin/env python3
"""Encar vehicle detail parser.

Reads a JSON payload with a `vehicleId`, fetches the corresponding Encar detail
page, extracts the preloaded JSON state, and returns normalized vehicle data.

Usage:
  echo '{"vehicleId": "40849700"}' | python parser.py
  # or parse an already-downloaded HTML (useful for offline testing):
  echo '{"vehicleId": "40849700"}' | python parser.py --html sample.html
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from unidecode import unidecode

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/107.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
}
REQUEST_TIMEOUT = 15
RETRY_STRATEGY = Retry(
    total=3,
    backoff_factor=0.3,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=("GET",),
)
SESSION = None  # Lazy-initialized shared session for connection reuse.


class EncarParseError(Exception):
    """Raised when the Encar page cannot be parsed."""


def build_session() -> requests.Session:
    """Return a configured session with retries."""
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=RETRY_STRATEGY)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(HEADERS)
    return session


def fetch_vehicle_page(vehicle_id: str, session: Optional[requests.Session] = None) -> str:
    """Download the vehicle detail page HTML."""
    url = f"https://fem.encar.com/cars/detail/{vehicle_id}"
    global SESSION
    if session:
        sess = session
    else:
        if SESSION is None:
            SESSION = build_session()
        sess = SESSION
    response = sess.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.text


def extract_preloaded_state(html: str) -> Dict[str, Any]:
    """Extract the __PRELOADED_STATE__ JSON blob embedded in the page."""
    marker = "__PRELOADED_STATE__"
    start = html.find(marker)
    if start == -1:
        raise EncarParseError("Preloaded state marker not found.")

    # Limit search to the current script tag for robustness.
    sliced = html[start:]
    end = sliced.find("</script>")
    if end == -1:
        raise EncarParseError("Closing script tag not found after preloaded state.")

    script_body = sliced[:end]
    _, _, tail = script_body.partition(marker)
    _, _, json_part = tail.partition("=")
    json_part = json_part.strip()
    if ";" in json_part:
        json_part = json_part.split(";", 1)[0]
    json_part = json_part.strip()

    try:
        return json.loads(json_part)
    except json.JSONDecodeError as exc:
        raise EncarParseError(f"Failed to decode preloaded state: {exc}") from exc


def normalize_price(raw_price: Optional[int]) -> Optional[int]:
    """Convert 가격(만원) to 원. Encar prices are expressed in 10,000 KRW."""
    if raw_price is None:
        return None
    return int(raw_price) * 10_000


def format_engine(displacement_cc: Optional[int]) -> Optional[str]:
    """Return a human-readable engine displacement string."""
    if displacement_cc in (None, 0):
        return None
    liters = displacement_cc / 1000
    trimmed = f"{liters:.1f}".rstrip("0").rstrip(".")
    return f"{trimmed}L"


def translate_transmission(value: Optional[str]) -> Optional[str]:
    mapping = {"오토": "Automatic", "수동": "Manual"}
    if not value:
        return None
    value = value.strip()
    return mapping.get(value, value)


def translate_fuel(value: Optional[str]) -> Optional[str]:
    mapping = {
        "가솔린": "Gasoline",
        "디젤": "Diesel",
        "하이브리드": "Hybrid",
        "전기": "Electric",
        "LPG": "LPG",
    }
    if not value:
        return None
    value = value.strip()
    return mapping.get(value, value)


def classify_fuel(spec: Dict[str, Any]) -> Optional[str]:
    """Return a normalized fuel category."""
    code_map = {
        "001": "Gasoline",
        "002": "Diesel",
        "003": "LPG",
        "004": "Electric",
        "005": "Hybrid",
        "006": "Hydrogen",
    }
    if spec.get("fuelCd") in code_map:
        return code_map[spec["fuelCd"]]
    return translate_fuel(spec.get("fuelName"))


COLOR_MAP = {
    "검정색": "Black",
    "흰색": "White",
    "화이트": "White",
    "은색": "Silver",
    "회색": "Gray",
    "빨간색": "Red",
    "파란색": "Blue",
    "청색": "Blue",
    "초록색": "Green",
    "갈색": "Brown",
    "베이지": "Beige",
    "노란색": "Yellow",
    "주황색": "Orange",
}


def to_english(text: Optional[str]) -> Optional[str]:
    """Best-effort translation/transliteration to English."""
    if not text:
        return None
    text = text.strip()
    if text in COLOR_MAP:
        return COLOR_MAP[text]
    # If ASCII already, return as-is; else transliterate to Latin.
    try:
        text.encode("ascii")
        return text
    except UnicodeEncodeError:
        return unidecode(text)


def extract_year(category: Dict[str, Any]) -> Optional[int]:
    if category.get("formYear"):
        return int(category["formYear"])
    year_month = str(category.get("yearMonth") or "")
    if len(year_month) >= 4 and year_month[:4].isdigit():
        return int(year_month[:4])
    return None


def format_date(date_str: Optional[str]) -> Optional[str]:
    """Return YYYY-MM-DD from an ISO datetime string."""
    if not date_str:
        return None
    return date_str.split("T", 1)[0]


def build_output(vehicle_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    base = state.get("cars", {}).get("base", {})
    category = base.get("category", {})
    advertisement = base.get("advertisement", {})
    spec = base.get("spec", {})
    manage = base.get("manage", {})
    condition_base = base.get("condition", {})

    specifications = {
        "engine": format_engine(spec.get("displacement")),
        "transmission": translate_transmission(spec.get("transmissionName")),
        "fuel_type": classify_fuel(spec),
        "color": to_english(spec.get("colorName")),
        "body_type": spec.get("bodyName"),
        "seats": spec.get("seatCount"),
    }
    specifications = {k: v for k, v in specifications.items() if v is not None}

    timestamps = {
        "registered_at": format_date(manage.get("registDateTime")),
        "first_advertised_at": format_date(manage.get("firstAdvertisedDateTime")),
        "modified_at": format_date(manage.get("modifyDateTime")),
    }
    timestamps = {k: v for k, v in timestamps.items() if v}

    metrics = {
        "view_count": manage.get("viewCount"),
        "favorite_count": manage.get("subscribeCount"),
        "ad_type": advertisement.get("advertisementType"),
        "ad_status": base.get("detailFlags", {}).get("adStatus") or advertisement.get("status"),
        "diagnosis_car": advertisement.get("diagnosisCar"),
    }
    metrics = {k: v for k, v in metrics.items() if v is not None}

    condition = {
        "accident_record_view": condition_base.get("accident", {}).get("recordView"),
        "inspection_formats": condition_base.get("inspection", {}).get("formats"),
        "seizing_count": condition_base.get("seizing", {}).get("seizingCount"),
        "pledge_count": condition_base.get("seizing", {}).get("pledgeCount"),
    }
    condition = {k: v for k, v in condition.items() if v is not None}

    data = {
        "id": str(base.get("vehicleId") or vehicle_id),
        "vin": base.get("vin"),
        "make": category.get("manufacturerEnglishName") or category.get("manufacturerName"),
        "model": category.get("modelGroupEnglishName")
        or category.get("modelGroupName")
        or category.get("modelName"),
        "trim": category.get("gradeEnglishName") or category.get("gradeName"),
        "year": extract_year(category),
        "price": normalize_price(advertisement.get("price")),
        "mileage": spec.get("mileage"),
        "fuel": classify_fuel(spec),
        "url": f"https://fem.encar.com/cars/detail/{vehicle_id}",
        "card_url": f"https://fem.encar.com/cars/detail/{vehicle_id}",
    }

    if specifications:
        data["specifications"] = specifications
    if timestamps:
        data["timestamps"] = timestamps
    if metrics:
        data["metrics"] = metrics
    if condition:
        data["condition"] = condition

    return {k: v for k, v in data.items() if v is not None}


def parse_vehicle(
    vehicle_id: str, html_path: Optional[str] = None, session: Optional[requests.Session] = None
) -> Dict[str, Any]:
    html = (
        Path(html_path).read_text(encoding="utf-8")
        if html_path
        else fetch_vehicle_page(vehicle_id, session=session)
    )
    state = extract_preloaded_state(html)
    return {"data": build_output(vehicle_id, state)}


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Parse an Encar vehicle detail page.")
    parser.add_argument("--html", dest="html_path", help="Path to a downloaded HTML page.")
    args = parser.parse_args(argv)

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid input JSON: {exc}") from exc

    vehicle_id = str(
        payload.get("vehicleId") or payload.get("id") or payload.get("vehicle_id") or ""
    ).strip()
    if not vehicle_id:
        raise SystemExit("Input JSON must contain `vehicleId`.")

    try:
        result = parse_vehicle(vehicle_id, html_path=args.html_path)
    except (requests.RequestException, EncarParseError) as exc:
        raise SystemExit(f"Failed to parse vehicle page: {exc}") from exc

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
