#!/usr/bin/env python3
"""Apify actor entrypoint for Encar vehicle parser."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, Dict, List

from apify import Actor

from parser import parse_vehicle


def _coerce_vehicle_ids(payload: Dict[str, Any]) -> List[str]:
    if "vehicleIds" in payload and isinstance(payload["vehicleIds"], list):
        return [str(v).strip() for v in payload["vehicleIds"] if str(v).strip()]
    if "vehicleId" in payload or "id" in payload:
        candidate = str(payload.get("vehicleId") or payload.get("id") or "").strip()
        return [candidate] if candidate else []
    return []


def _cli_html_path(argv: List[str]) -> Optional[str]:
    if "--html" in argv:
        idx = argv.index("--html")
        if idx + 1 < len(argv):
            return argv[idx + 1]
    return None


async def main() -> None:
    """Run in Apify if available, else fallback to local stdin/stdout."""
    if os.environ.get("APIFY_IS_AT_HOME") == "1":
        async with Actor:
            payload = await Actor.get_input() or {}
            vehicle_ids = _coerce_vehicle_ids(payload)
            html_path = payload.get("htmlPath")

            if not vehicle_ids:
                await Actor.fail("Input must contain `vehicleId` or `vehicleIds`.")
                return

            results = []
            for vehicle_id in vehicle_ids:
                try:
                    results.append(parse_vehicle(vehicle_id, html_path=html_path))
                except Exception as exc:  # noqa: BLE001
                    await Actor.log.exception(f"Failed to parse vehicle {vehicle_id}: {exc}")

            for item in results:
                await Actor.push_data(item)
            await Actor.set_value(
                "OUTPUT", results if len(results) > 1 else (results[0] if results else {})
            )
    else:
        # Local fallback: read JSON from stdin and print result.
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid input JSON: {exc}") from exc
        vehicle_ids = _coerce_vehicle_ids(payload)
        html_path = payload.get("htmlPath") or _cli_html_path(sys.argv[1:])
        if not vehicle_ids:
            raise SystemExit("Input must contain `vehicleId` or `vehicleIds`.")
        results = [parse_vehicle(vehicle_id, html_path=html_path) for vehicle_id in vehicle_ids]
        output = results if len(results) > 1 else results[0]
        json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    asyncio.run(main())
