"""Low-frequency ARAMKit version discovery with a hard rate-limit stop."""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable


DISCOVERY_URLS = ("https://aramkit.com/zh-CN/champions", "https://aramkit.com/zh-CN/terms")
USER_AGENT = "Mozilla/5.0 (compatible; aram-guide-version-check/1.0)"


class UpdateError(RuntimeError):
    pass


class TerminalHttpError(UpdateError):
    pass


def fetch_url(
    url: str,
    *,
    as_json: bool = False,
    opener: Callable[..., Any] = urllib.request.urlopen,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with opener(request, timeout=30) as response:
                raw = response.read()
            return json.loads(raw.decode("utf-8")) if as_json else raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                raise TerminalHttpError(f"HTTP {exc.code}: {url}") from exc
            if exc.code < 500:
                raise UpdateError(f"HTTP {exc.code}: {url}") from exc
            last_error = exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
        if attempt < 2:
            sleep(0.5 * (2**attempt))
    raise UpdateError(f"request failed: {url}: {last_error}") from last_error


def parse_discovery_page(html: str) -> dict[str, Any]:
    endpoint = re.search(r'aramKitDataEndpoint:\s*"([^"]+)"', html)
    latest_match = re.search(r'aramKitDataVersions:\s*\{\s*latest:\s*"([^"]+)"', html)
    entries = re.findall(
        r'\{version:\s*"([^"]+)",dataPath:\s*"([^"]+)",resourcePath:\s*"([^"]+)"'
        r',allMatches:\s*(\d+),highMatches:\s*(\d+),dataDate:\s*"([^"]+)"\}',
        html,
    )
    if not endpoint or not entries:
        raise UpdateError("ARAMKit discovery markup changed")
    latest = latest_match.group(1) if latest_match else entries[0][0]
    chosen = next((entry for entry in entries if entry[0] == latest), entries[0])
    return {
        "endpoint": endpoint.group(1).rstrip("/"),
        "version": chosen[0],
        "dataPath": chosen[1].strip("/"),
        "resourcePath": chosen[2].strip("/"),
        "allMatches": int(chosen[3]),
        "highMatches": int(chosen[4]),
        "dataDate": chosen[5],
    }


def discover_latest() -> dict[str, Any]:
    last_error: Exception | None = None
    for url in DISCOVERY_URLS:
        try:
            return parse_discovery_page(fetch_url(url))
        except TerminalHttpError:
            raise
        except UpdateError as exc:
            last_error = exc
    raise UpdateError(f"version discovery failed: {last_error}") from last_error


def check_for_update(
    current: dict[str, Any],
    discover: Callable[[], dict[str, Any]] = discover_latest,
    *,
    detail_fetch: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    latest = discover()
    unchanged = (
        str(current.get("version")) == str(latest.get("version"))
        and str(current.get("dataDate")) == str(latest.get("dataDate"))
    )
    return {
        **latest,
        "status": "unchanged" if unchanged else "changed",
        "changed": not unchanged,
        "current": {"version": current.get("version"), "dataDate": current.get("dataDate")},
        "detailRequests": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-index", type=Path, default=Path("data/index.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/update-check.json"))
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    index = json.loads(args.current_index.read_text(encoding="utf-8"))
    result = check_for_update(index["site"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write(f'changed={str(result["changed"]).lower()}\n')
            stream.write(f'metadata={args.output.as_posix()}\n')
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
