#!/usr/bin/env python3
"""Apify actor entrypoint for Encar vehicle parser."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

from apify import Actor

from parser import build_session, parse_vehicle


# Limit how many parsed items we keep in OUTPUT to avoid blowing KV store for bulk runs.
OUTPUT_ITEM_LIMIT = 20


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


def _parse_max_concurrency(payload: Dict[str, Any]) -> int:
    raw_value = payload.get("maxConcurrency")
    if raw_value is None:
        value = 3
    else:
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            value = 3
    # Keep within a conservative range to respect site limits and Apify resources.
    return max(1, min(value, 10))


async def _process_vehicle_ids(
    vehicle_ids: List[str],
    html_path: Optional[str],
    max_concurrency: int,
    *,
    store_limit: Optional[int],
    push_to_dataset: bool,
) -> Tuple[List[Dict[str, Any]], int, List[Tuple[str, str]]]:
    """Process vehicle IDs with bounded concurrency and optional storage limit."""

    total = len(vehicle_ids)
    worker_count = min(max_concurrency, total)
    queue: asyncio.Queue[Optional[Tuple[int, str]]] = asyncio.Queue()
    for idx, vehicle_id in enumerate(vehicle_ids):
        queue.put_nowait((idx, vehicle_id))
    for _ in range(worker_count):
        queue.put_nowait(None)

    results: List[Tuple[int, Dict[str, Any]]] = []
    failures: List[Tuple[str, str]] = []
    success_count = 0
    processed = 0
    last_status = 0

    sessions = [None if html_path else build_session() for _ in range(worker_count)]

    async def worker(worker_idx: int) -> None:
        nonlocal success_count, processed, last_status
        session = sessions[worker_idx]
        try:
            while True:
                queued = await queue.get()
                if queued is None:
                    queue.task_done()
                    break
                order_idx, vehicle_id = queued
                try:
                    result = await asyncio.to_thread(
                        parse_vehicle, vehicle_id, html_path=html_path, session=session
                    )
                    success_count += 1
                    if store_limit is None or len(results) < store_limit:
                        results.append((order_idx, result))
                    if push_to_dataset:
                        await Actor.push_data(result)
                except Exception as exc:  # noqa: BLE001
                    failures.append((vehicle_id, str(exc)))
                finally:
                    processed += 1
                    if push_to_dataset and processed - last_status >= 5:
                        last_status = processed
                        update_fn = getattr(Actor, "update_status_message", None)
                        if update_fn:
                            await update_fn(f"Processed {processed}/{total} vehicles")
                    queue.task_done()
        finally:
            if session is not None:
                session.close()

    workers = [asyncio.create_task(worker(idx)) for idx in range(worker_count)]
    await queue.join()
    await asyncio.gather(*workers)

    # Restore input order for stored results/preview.
    ordered_results = [item for _, item in sorted(results, key=lambda pair: pair[0])]

    return ordered_results, success_count, failures


async def main() -> None:
    """Run in Apify if available, else fallback to local stdin/stdout."""
    if os.environ.get("APIFY_IS_AT_HOME") == "1":
        async with Actor:
            payload = await Actor.get_input() or {}
            vehicle_ids = _coerce_vehicle_ids(payload)
            html_path = payload.get("htmlPath")
            max_concurrency = _parse_max_concurrency(payload)

            if not vehicle_ids:
                await Actor.fail("Input must contain `vehicleId` or `vehicleIds`.") # pyright: ignore[reportCallIssue]
                return

            store_limit = None if len(vehicle_ids) == 1 else OUTPUT_ITEM_LIMIT
            results, success_count, failures = await _process_vehicle_ids(
                vehicle_ids,
                html_path=html_path,
                max_concurrency=max_concurrency,
                store_limit=store_limit,
                push_to_dataset=True,
            )

            output: Dict[str, Any] = { # pyright: ignore[reportRedeclaration]
                "total": len(vehicle_ids),
                "succeeded": success_count,
                "failed": [
                    {"vehicleId": vehicle_id, "error": error} for vehicle_id, error in failures
                ],
            }

            # Preserve compatibility for single runs by returning the item directly.
            if len(vehicle_ids) == 1 and results:
                output["item"] = results[0]
            elif results:
                if len(results) >= success_count:
                    output["items"] = results
                else:
                    output["itemsPreview"] = results
                    output["itemsPreviewCount"] = len(results)
                    output["itemsTotal"] = success_count
                    output["itemsTruncated"] = True

            await Actor.set_value("OUTPUT", output)
    else:
        # Local fallback: read JSON from stdin and print result.
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid input JSON: {exc}") from exc
        vehicle_ids = _coerce_vehicle_ids(payload)
        html_path = payload.get("htmlPath") or _cli_html_path(sys.argv[1:])
        max_concurrency = _parse_max_concurrency(payload)
        if not vehicle_ids:
            raise SystemExit("Input must contain `vehicleId` or `vehicleIds`.")
        results, success_count, failures = await _process_vehicle_ids(
            vehicle_ids,
            html_path=html_path,
            max_concurrency=max_concurrency,
            store_limit=None,
            push_to_dataset=False,
        )
        if failures:
            sys.stderr.write(
                "\n".join([f"Failed {vid}: {err}" for vid, err in failures]) + "\n"
            )
        output: Union[List[Dict[str, Any]], Dict[str, Any]]
        output = results if len(vehicle_ids) > 1 else (results[0] if results else {})
        json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    asyncio.run(main())
