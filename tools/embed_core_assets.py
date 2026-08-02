from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "index.html"
STYLE_PATH = ROOT / "styles.css"
APP_PATH = ROOT / "app.js"
ANALYTICS_CONFIG_PATH = ROOT / "analytics-config.js"
ANALYTICS_PATH = ROOT / "analytics.js"

STYLE_START = "<!-- compat-core-style:start -->"
STYLE_END = "<!-- compat-core-style:end -->"
APP_START = "<!-- compat-core-app:start -->"
APP_END = "<!-- compat-core-app:end -->"
ANALYTICS_START = "<!-- compat-core-analytics:start -->"
ANALYTICS_END = "<!-- compat-core-analytics:end -->"


def replace_region(source: str, start: str, end: str, content: str) -> str:
    before, separator, remainder = source.partition(start)
    if not separator:
        raise ValueError(f"missing marker: {start}")
    _, separator, after = remainder.partition(end)
    if not separator:
        raise ValueError(f"missing marker: {end}")
    return f"{before}{start}\n{content}\n{end}{after}"


def rendered_index() -> str:
    html = INDEX_PATH.read_text(encoding="utf-8")
    css = STYLE_PATH.read_text(encoding="utf-8").rstrip()
    app = APP_PATH.read_text(encoding="utf-8").rstrip()
    analytics = "\n".join((
        ANALYTICS_CONFIG_PATH.read_text(encoding="utf-8").rstrip(),
        ANALYTICS_PATH.read_text(encoding="utf-8").rstrip(),
    ))
    if "</style" in css.lower() or "</script" in app.lower() or "</script" in analytics.lower():
        raise ValueError("core asset contains an unsafe closing tag")
    html = replace_region(
        html,
        STYLE_START,
        STYLE_END,
        f'<style data-compat-core="styles">\n{css}\n</style>',
    )
    html = replace_region(
        html,
        ANALYTICS_START,
        ANALYTICS_END,
        f'<script data-compat-core="analytics">\n{analytics}\n</script>',
    )
    return replace_region(
        html,
        APP_START,
        APP_END,
        f'<script data-compat-core="app">\n{app}\n</script>',
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Embed the editable CSS and app sources into the static HTML shell.",
    )
    parser.add_argument("--check", action="store_true", help="fail when index.html is stale")
    args = parser.parse_args()

    expected = rendered_index()
    current = INDEX_PATH.read_text(encoding="utf-8")
    if args.check:
        if current != expected:
            print("index.html core assets are stale; run tools/embed_core_assets.py")
            return 1
        return 0

    INDEX_PATH.write_text(expected, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
