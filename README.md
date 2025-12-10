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
- Валидация структуры `cars.base.*` через Pydantic: при изменениях HTML/state выдаёт понятные ошибки вместо тихих падений.

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
- Важно: `parser.py` валидирует `cars.base.*` (Pydantic) и бросает `EncarParseError` с деталями, если Encar меняет структуру.
- `main.py`: Apify actor entrypoint + local fallback.
- `requirements.txt`: dependencies (`requests`, `Unidecode`, `apify`, `pydantic`).
- `Dockerfile`: build for Apify platform.
- `apify.json`: actor metadata.
- `sample.html`: fixture for offline testing.

## Running Locally

1. Install deps (venv recommended):

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

2. Parse live (network required):

```bash
echo '{"vehicleId": "40849700"}' | .venv/bin/python main.py
```

3. Parse offline:

```bash
echo '{"vehicleId": "40849700"}' | .venv/bin/python main.py --html sample.html
```

4. Multiple IDs:

```bash
echo '{"vehicleIds": ["40849700", "12345678"]}' | .venv/bin/python main.py
```

## Apify Usage

- Deploy this repository as an Apify actor.
- Input `INPUT.json` with `vehicleId` or `vehicleIds`.
- Actor handles networking, pushes results to the default dataset, and saves `OUTPUT`.
- CI/CD: GitHub Actions workflow `.github/workflows/apify-deploy.yml` runs `apify push` on pushes to `main/master`. Add `APIFY_TOKEN` to repo secrets; never commit tokens or .env files (they’re gitignored).
- При ошибках парсинга/валидации получите `EncarParseError` с указанием поля; используйте `sample.html` и тесты для диагностики.

## Диагностика и типовые ошибки

### Примеры сообщений валидации

- `EncarParseError: State missing cars object.` — в `__PRELOADED_STATE__` нет блока `cars`; проверьте, не изменилась ли структура страницы.
- `EncarParseError: State missing cars.base object.` — отсутствует ключевой объект `base`; возможно, Encar сменил вложенность.
- `EncarParseError: cars.base validation failed: Field required @ category` — `cars.base.category` отсутствует или имеет неверный тип.
- `EncarParseError: cars.base validation failed: Input should be a valid integer @ spec/displacement` — тип поля изменился (например, строка вместо числа).
- `EncarParseError: Preloaded state marker not found.` — в HTML нет `__PRELOADED_STATE__`; страница может быть иной версии или доступ заблокирован.

### Локальная проверка и воспроизведение

1. Запустить тесты на фикстуре:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

2. Прогнать парсер на `sample.html`:

```bash
echo '{"vehicleId": "40849700"}' | python3 main.py --html sample.html
```

3. Если есть новый HTML:

```bash
echo '{"vehicleId": "NEW_ID"}' | python3 main.py --html path/to/new.html
```

4. Для сетевых запросов убедитесь, что установлены зависимости (`pip install -r requirements.txt`) и есть доступ к `https://fem.encar.com`.

### Что делать при ошибках

- Снимите свежую страницу в файл и запустите парсер с `--html`, чтобы исключить сетевые проблемы.
- Сравните структуру `__PRELOADED_STATE__` с ожиданиями (см. `tests/test_parser.py` и модели в `parser.py`).
- При изменениях структуры обновите Pydantic-модели (`BaseCarModel` и вложенные) и логику нормализации в `build_output`.

## Notes and Limits

- Relies on the embedded `__PRELOADED_STATE__`; if Encar changes page structure, update the extractor.
- Price is normalized to KRW (만원 \* 10,000).
- Color translations use a simple dictionary; extend `COLOR_MAP` as needed.
- Network errors are retried (3 attempts) with a backoff of 0.3s on common HTTP status codes.
