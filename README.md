# Encar Vehicle Parser

Parse Encar vehicle detail pages (`https://fem.encar.com/cars/detail/{vehicleId}`) and return normalized JSON. Works as both a local CLI tool and an Apify actor.

## What It Does
- Fetches the detail page and extracts the `__PRELOADED_STATE__` JSON (no browser needed).
- Validates the critical `cars.base.*` shape with Pydantic to surface breaking site changes early.
- Normalizes key fields: id, VIN, make/model/trim, year, price (만원 → KRW), mileage, specs (engine, transmission, fuel, color, body, seats), timestamps (dates only), metrics (views/favorites/ad flags), and condition flags.
- Supports one or many `vehicleId` inputs; outputs an object for one or a list for many.

## Quickstart (Local)
1) Install deps (virtualenv recommended):
```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```
2) Parse live (requires network):
```bash
echo '{"vehicleId": "40849700"}' | python main.py
```
3) Parse offline with a saved page:
```bash
echo '{"vehicleId": "40849700"}' | python main.py --html sample.html
```
4) Multiple IDs:
```bash
echo '{"vehicleIds": ["40849700", "12345678"]}' | python main.py
```

## Sample Output
```json
{
  "data": {
    "id": "40837591",
    "vin": "KNAPN813BGK034698",
    "make": "Kia",
    "model": "Sportage",
    "trim": "Diesel 2WD Noblesse",
    "year": 2016,
    "price": 10500000,
    "mileage": 165182,
    "fuel": "Diesel",
    "url": "https://fem.encar.com/cars/detail/40849700",
    "card_url": "https://fem.encar.com/cars/detail/40849700",
    "specifications": {
      "engine": "2L",
      "transmission": "Automatic",
      "fuel_type": "Diesel",
      "color": "Black",
      "body_type": "SUV",
      "seats": 5
    },
    "timestamps": {
      "registered_at": "2025-10-29",
      "first_advertised_at": "2025-10-30",
      "modified_at": "2025-12-08"
    },
    "metrics": {
      "view_count": 330,
      "favorite_count": 1,
      "ad_type": "NORMAL",
      "ad_status": "ADVERTISE",
      "diagnosis_car": true
    },
    "condition": {
      "accident_record_view": true,
      "inspection_formats": ["TABLE"],
      "seizing_count": 0,
      "pledge_count": 0
    }
  }
}
```

## Validation & Error Messages
Key fields under `cars.base.*` are validated. Typical errors:
- `EncarParseError: State missing cars object.` — `__PRELOADED_STATE__` is missing `cars`.
- `EncarParseError: State missing cars.base object.` — `cars.base` not found.
- `EncarParseError: cars.base validation failed: Field required @ category` — expected `category` block is absent.
- `EncarParseError: cars.base validation failed: Input should be a valid integer @ spec/displacement` — type changed on the site.
- `EncarParseError: Preloaded state marker not found.` — page missing `__PRELOADED_STATE__` (different variant or blocked response).

## Troubleshooting
1) Run tests against the fixture:
```bash
python -m unittest discover -s tests -p 'test_*.py'
```
2) Reproduce offline with a saved page:
```bash
echo '{"vehicleId": "40849700"}' | python main.py --html sample.html
```
3) With a fresh HTML:
```bash
echo '{"vehicleId": "NEW_ID"}' | python main.py --html path/to/new.html
```
4) If parsing fails:
- Grab a fresh page, rerun with `--html` to rule out network.
- Inspect `__PRELOADED_STATE__` and align Pydantic models in `parser.py` (`BaseCarModel` and nested models).
- Update normalization in `build_output` if fields moved or renamed.

## Project Layout
- `parser.py` — fetch, state extraction, Pydantic validation, normalization.
- `main.py` — Apify actor entrypoint + local CLI fallback.
- `tests/test_parser.py` — fixture-based unit tests and negative cases.
- `requirements.txt` — deps: `requests`, `Unidecode`, `apify`, `pydantic`.
- `Dockerfile` — container build for Apify.
- `sample.html` — saved page for offline runs/tests.

## Apify Usage
- Deploy as an Apify actor; provide `vehicleId` or `vehicleIds` in `INPUT.json`.
- Actor pushes results to the default dataset and stores `OUTPUT`.
- GitHub Actions (`.github/workflows/apify-deploy.yml`) can push on `main/master` when secrets (`APIFY_TOKEN`, `APIFY_ACTOR_ID`) are set.

## Notes
- Prices are converted from 만원 to KRW.
- Colors are best-effort translated; extend `COLOR_MAP` in `parser.py` if needed.
- HTTP requests use a shared session with retries (3 attempts, backoff 0.3s on common 5xx/429).***
