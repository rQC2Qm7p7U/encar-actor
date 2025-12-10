# Encar Vehicle Parser (Apify Actor)

Parses Encar vehicle detail pages (e.g., `https://fem.encar.com/cars/detail/{vehicleId}`) and outputs structured JSON with key fields: id, VIN, make/model/trim, price, mileage, specifications, timestamps, metrics, and condition flags.

## Features
- Single or multiple `vehicleId` inputs.
- Uses preloaded `__PRELOADED_STATE__` JSON (no dynamic rendering needed).
- Converts price from 만원 to KRW.
- English-friendly specs (engine, transmission, fuel, color, body type, seats).
- Includes VIN, trim, fuel (top-level), timestamps (date-only), metrics (views/favorites/ad flags), and condition info.
- Reuses HTTP session and retry strategy for robustness.
- Works as an Apify actor and as a local CLI tool (fallback mode).

## Input
JSON via Apify input or stdin (local):
```json
{
  "vehicleId": "40849700"
}
```
or
```json
{
  "vehicleIds": ["40849700", "12345678"]
}
```
Optional (local/offline):
- `htmlPath`: path to a downloaded Encar detail page.
- CLI flag `--html path/to/file` (local fallback).

## Output
For each vehicle:
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
- Single input returns an object; multiple inputs return an array.
- In Apify, results are also pushed to the default dataset and stored as `OUTPUT`.

## Project Layout
- `parser.py`: core parser logic (HTML fetch, preloaded state extraction, normalization).
- `main.py`: Apify actor entrypoint + local fallback.
- `requirements.txt`: dependencies (`requests`, `Unidecode`, `apify`).
- `Dockerfile`: build for Apify platform.
- `apify.json`: actor metadata.
- `sample.html`: fixture for offline testing.

## Running Locally
1) Install deps (venv recommended):
```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```
2) Parse live (network required):
```bash
echo '{"vehicleId": "40849700"}' | .venv/bin/python main.py
```
3) Parse offline:
```bash
echo '{"vehicleId": "40849700"}' | .venv/bin/python main.py --html sample.html
```
4) Multiple IDs:
```bash
echo '{"vehicleIds": ["40849700", "12345678"]}' | .venv/bin/python main.py
```

## Apify Usage
- Deploy this repository as an Apify actor.
- Input `INPUT.json` with `vehicleId` or `vehicleIds`.
- Actor handles networking, pushes results to the default dataset, and saves `OUTPUT`.
- CI/CD: GitHub Actions workflow `.github/workflows/apify-deploy.yml` runs `apify push` on pushes to `main/master`. Add `APIFY_TOKEN` to repo secrets; never commit tokens or .env files (they’re gitignored).

## Notes and Limits
- Relies on the embedded `__PRELOADED_STATE__`; if Encar changes page structure, update the extractor.
- Price is normalized to KRW (만원 * 10,000).
- Color translations use a simple dictionary; extend `COLOR_MAP` as needed.
- Network errors are retried (3 attempts) with a backoff of 0.3s on common HTTP status codes.
