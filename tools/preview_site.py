"""Validate the complete site, then serve it for local acceptance."""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import re
import subprocess
import sys
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parents[1]


def run_checks(site_dir: Path) -> dict[str, int | str]:
    subprocess.run(
        [sys.executable, str(site_dir / "tools" / "embed_core_assets.py"), "--check"],
        cwd=site_dir,
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        cwd=site_dir,
        check=True,
    )

    index_path = site_dir / "data" / "index.json"
    data = json.loads(index_path.read_text(encoding="utf-8"))
    guides = data.get("guides") or []
    published_count = data.get("site", {}).get("guideCount")
    if published_count != len(guides):
        raise ValueError(f"guideCount={published_count}，实际攻略={len(guides)}")

    revision_values: set[str] = set()
    for name in ("index.html", "app.js", "sw.js"):
        revision_values.update(re.findall(r"rev=(\d+)", (site_dir / name).read_text(encoding="utf-8")))
    if len(revision_values) != 1:
        raise ValueError(f"缓存版本不一致: {sorted(revision_values)}")

    build_count = 0
    for guide in guides:
        hero_path = site_dir / "data" / "heroes" / f"{guide['slug']}.json"
        hero = json.loads(hero_path.read_text(encoding="utf-8"))
        builds = hero.get("builds") or []
        if not builds:
            raise ValueError(f"英雄缺少流派: {guide['slug']}")
        build_count += len(builds)

    if build_count <= len(guides):
        raise ValueError(f"流派总数异常：英雄={len(guides)}，流派={build_count}")

    return {
        "guides": len(guides),
        "builds": build_count,
        "revision": revision_values.pop(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8879)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    summary = run_checks(SITE_ROOT)
    print(json.dumps(summary, ensure_ascii=False))
    if args.check_only:
        return 0

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE_ROOT))
    server = http.server.ThreadingHTTPServer((args.host, args.port), handler)
    print(f"本地验收地址：http://{args.host}:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
