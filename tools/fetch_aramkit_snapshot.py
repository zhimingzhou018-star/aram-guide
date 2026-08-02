"""Fetch an immutable ARAMKit raw snapshot without changing published data."""

from __future__ import annotations

import argparse
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

try:
    from tools.check_aramkit_update import fetch_url
except ModuleNotFoundError:
    from check_aramkit_update import fetch_url


class SnapshotError(RuntimeError):
    pass


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class Throttle:
    def __init__(self, interval: float, sleep: Callable[[float], None]):
        self.interval = interval
        self.sleep = sleep
        self.lock = threading.Lock()
        self.last_started = 0.0

    def wait(self) -> None:
        with self.lock:
            delay = self.interval - (time.monotonic() - self.last_started)
            if delay > 0:
                self.sleep(delay)
            self.last_started = time.monotonic()


def fetch_snapshot(
    metadata: dict[str, Any],
    snapshots_root: Path,
    *,
    current_manifest: Path | None = None,
    fetch_json: Callable[[str], Any] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    max_workers: int = 2,
    request_interval: float = 0.5,
) -> Path:
    key = f'{metadata["version"]}-{str(metadata["dataDate"]).replace("-", "")}'
    final_dir = snapshots_root / key
    if final_dir.exists():
        return final_dir

    staging = snapshots_root / ".staging" / f"{key}-{uuid.uuid4().hex[:8]}"
    raw_dir = staging / "raw"
    raw_dir.mkdir(parents=True, exist_ok=False)
    throttle = Throttle(request_interval, sleep)

    if fetch_json is None:
        def fetch_json(url: str) -> Any:
            return fetch_url(url, as_json=True)

    def guarded_fetch(url: str) -> Any:
        throttle.wait()
        return fetch_json(url)

    endpoint = str(metadata["endpoint"]).rstrip("/")
    resource_base = f'{endpoint}/{str(metadata["resourcePath"]).strip("/")}/zh-CN/resources'
    stats_base = f'{endpoint}/{str(metadata["dataPath"]).strip("/")}/stats/all'
    resources: dict[str, Any] = {}
    try:
        for name in ("champions", "items", "augments", "summoner-spells"):
            resources[name] = guarded_fetch(f"{resource_base}/{name}.json")
            write_json(raw_dir / f"{name}.json", resources[name])

        rankings = guarded_fetch(f"{stats_base}/champion-rankings.json")
        rows = rankings.get("rows") if isinstance(rankings, dict) else None
        if not isinstance(rows, list) or not rows:
            raise SnapshotError("champion rankings are empty")
        write_json(raw_dir / "champion-rankings.json", rankings)

        def fetch_detail(champion_id: int) -> tuple[int, Any]:
            payload = guarded_fetch(f"{stats_base}/champion-details/{champion_id}.json")
            actual_id = payload.get("champion", {}).get("id") if isinstance(payload, dict) else None
            if int(actual_id or -1) != champion_id:
                raise SnapshotError(f"invalid champion detail: expected {champion_id}, got {actual_id}")
            return champion_id, payload

        with ThreadPoolExecutor(max_workers=max(1, min(2, max_workers))) as executor:
            futures = [executor.submit(fetch_detail, int(row["id"])) for row in rows]
            for future in as_completed(futures):
                champion_id, payload = future.result()
                write_json(raw_dir / "champion-details" / f"{champion_id}.json", payload)

        write_json(staging / "manifest.json", {
            "status": "candidate",
            "provider": "ARAMKit",
            "region": "unknown",
            "dataLevel": "aggregate",
            "segment": "all",
            "version": metadata["version"],
            "dataDate": metadata["dataDate"],
            "heroCount": len(rows),
            "manualApprovalRequired": True,
            "published": False,
        })
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        staging.rename(final_dir)
        return final_dir
    except Exception as exc:
        write_json(staging / "FAILED.json", {"error": str(exc), "currentManifestUntouched": True})
        if isinstance(exc, SnapshotError):
            raise
        raise SnapshotError(str(exc)) from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--snapshots-root", type=Path, default=Path("snapshots"))
    parser.add_argument("--current-manifest", type=Path, default=Path("data/index.json"))
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    path = fetch_snapshot(metadata, args.snapshots_root, current_manifest=args.current_manifest)
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write(f"candidate={path.as_posix()}\n")
    print(path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
