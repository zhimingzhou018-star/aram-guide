"""Build the modular, per-hero static data used by the V2 guide site."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from PIL import Image

try:
    from tools.guide_schema import validate_guide
except ModuleNotFoundError:  # Support `python tools/build_modular_data.py`.
    from guide_schema import validate_guide


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
ALIASES_PATH = WORKTREE_ROOT / "config" / "search-aliases.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def unique_text(*groups: Any) -> list[str]:
    values: list[str] = []
    for group in groups:
        rows = group if isinstance(group, list) else [group]
        for row in rows:
            text = str(row or "").strip()
            if text and text not in values:
                values.append(text)
    return values


def percent(value: Any) -> float | None:
    return None if value is None else round(float(value) * 100, 2)


def copy_webp(source: Path, destination: Path) -> bool:
    if not source.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image.convert("RGBA").save(destination, "WEBP", lossless=True, method=6)
    return True


class ResourceCatalog:
    def __init__(self, project_root: Path, output_root: Path, copy_assets: bool):
        self.project_root = project_root
        self.output_root = output_root
        self.copy_assets = copy_assets
        self.items: dict[str, dict[str, Any]] = {}
        self.augments: dict[str, dict[str, Any]] = {}
        self.summoner_spells: dict[str, dict[str, Any]] = {}

    def item(self, row: dict[str, Any]) -> dict[str, Any]:
        item_id = int(row["id"])
        icon = f"assets/resources/items/{item_id}.webp"
        enriched = {**row, "id": item_id, "icon": icon}
        self.items[str(item_id)] = {"id": item_id, "name": row["name"], "icon": icon}
        if self.copy_assets:
            copy_webp(
                self.project_root / "data" / "archive" / "assets" / "items" / f"{item_id}.png",
                self.output_root / icon,
            )
        return enriched

    def augment(self, row: dict[str, Any], rarity: str) -> dict[str, Any]:
        augment_id = int(row["id"])
        icon = f"assets/resources/augments/{augment_id}.webp"
        enriched = {**row, "id": augment_id, "rarity": rarity, "icon": icon}
        self.augments[str(augment_id)] = {
            "id": augment_id,
            "name": row["name"],
            "rarity": rarity,
            "icon": icon,
        }
        if self.copy_assets:
            metadata_path = self.project_root / "data" / "archive" / "hexes" / f"{augment_id}.json"
            if metadata_path.exists():
                metadata = read_json(metadata_path)
                source = self.project_root / "data" / "archive" / metadata.get("icon_path", "")
                copy_webp(source, self.output_root / icon)
        return enriched

    def ensure_augment(self, augment_id: Any, name: str) -> None:
        key = str(int(augment_id))
        if key not in self.augments:
            self.augment({"id": int(augment_id), "name": name}, "combination")

    def summoner_spell(self, row: dict[str, Any]) -> dict[str, Any]:
        spell_id = int(row["id"])
        icon = f"assets/resources/summoner-spells/{spell_id}.webp"
        enriched = {**row, "id": spell_id, "icon": icon}
        self.summoner_spells[str(spell_id)] = {"id": spell_id, "name": row["name"], "icon": icon}
        if self.copy_assets:
            metadata_path = self.project_root / "data" / "archive" / "summoner_spells" / f"{spell_id}.json"
            if metadata_path.exists():
                metadata = read_json(metadata_path)
                source = self.project_root / "data" / "archive" / metadata.get("icon_path", "")
                copy_webp(source, self.output_root / icon)
        return enriched

    def ability_icons(self, riot_id: str, skill_order: str) -> list[dict[str, str]]:
        result = []
        for key in skill_order.split(">"):
            icon = f"assets/resources/abilities/{riot_id}-{key}.webp"
            result.append({"key": key, "icon": icon})
            if self.copy_assets:
                copy_webp(
                    self.project_root / "data" / "archive" / "assets" / "abilities" / f"{riot_id}_{key}.png",
                    self.output_root / icon,
                )
        return result

    def write(self) -> None:
        resources = self.output_root / "data" / "resources"
        write_json(resources / "items.json", self.items)
        write_json(resources / "augments.json", self.augments)
        write_json(resources / "summoner-spells.json", self.summoner_spells)


def transform_guide(
    reviewed: dict[str, Any],
    source: dict[str, Any],
    legacy: dict[str, Any],
    aliases: list[str],
    resources: ResourceCatalog,
) -> dict[str, Any]:
    champion = reviewed["champion"]
    champion_id = int(champion["id"])
    slug = champion["slug"]
    riot_id = champion["riotId"]
    ranking = reviewed["ranking"]
    gameplay = reviewed["gameplay"]
    skill_order = reviewed["skillOrder"]
    reviewed_builds = reviewed.get("builds") or [{
        **reviewed["build"],
        "starterItems": reviewed["starterItems"],
        "coreItems": reviewed["coreItems"],
        "recommendedItems": reviewed["recommendedItems"],
    }]
    builds = []
    for build in reviewed_builds:
        builds.append({
            **{
                key: value
                for key, value in build.items()
                if key not in {"starterItems", "coreItems", "recommendedItems"}
            },
            "items": {
                "starter": [resources.item(row) for row in build["starterItems"]],
                "core": [resources.item(row) for row in build["coreItems"]],
                "recommended": [resources.item(row) for row in build["recommendedItems"]],
            },
        })
    primary_build = builds[0]
    primary_items = primary_build["items"]
    augment_rows: dict[str, list[dict[str, Any]]] = {}
    for rarity in ("prismatic", "gold", "silver"):
        augment_rows[rarity] = [resources.augment(row, rarity) for row in reviewed["augments"][rarity]]
    for combination in reviewed["augmentCombinations"]:
        for augment_id, name in zip(combination.get("augmentIds", []), combination.get("names", [])):
            resources.ensure_augment(augment_id, name)

    guide = {
        "schemaVersion": 3,
        "hero": {
            "id": champion_id,
            "slug": slug,
            "riotId": riot_id,
            "name": champion["name"],
            "title": champion["title"],
            "aliases": unique_text(champion.get("aliases", []), legacy.get("aliases", []), aliases),
            "roles": champion.get("roles", []),
            "icon": legacy.get("icon") or f"assets/champions/{slug}.webp",
            "abilities": resources.ability_icons(riot_id, skill_order),
        },
        "ranking": {
            **ranking,
            "winRatePercent": percent(ranking.get("winRate")),
            "pickRatePercent": percent(ranking.get("pickRate")),
        },
        "build": {
            key: value
            for key, value in primary_build.items()
            if key != "items"
        },
        "defaultBuildKey": primary_build["key"],
        "builds": builds,
        "summonerSpells": [resources.summoner_spell(row) for row in reviewed["summonerSpells"]],
        "skillOrder": skill_order,
        "items": primary_items,
        "augments": {
            **augment_rows,
            "combinations": [
                {
                    **row,
                    "ids": [int(value) for value in row.get("augmentIds", [])],
                }
                for row in reviewed["augmentCombinations"]
            ],
        },
        "gameplay": {
            "status": "reviewed",
            "locked": True,
            "source": gameplay.get("source"),
            "summary": gameplay["summary"],
        },
        "sources": [
            {
                "provider": "ARAMKit",
                "version": source["version"],
                "dataDate": source["dataDate"],
                "region": "unknown",
                "dataLevel": "aggregate",
                "segment": reviewed.get("statisticsSegment", source.get("segment", "all")),
                **(
                    {"fallbackReason": reviewed["segmentFallbackReason"]}
                    if reviewed.get("segmentFallbackReason")
                    else {}
                ),
            },
            {
                "provider": gameplay.get("sourceProvider", "ARAMGG"),
                "version": gameplay.get("sourceVersion"),
                "url": gameplay.get("source"),
                "usage": "editorial-reference",
            },
        ],
        "legacy": {"poster": (legacy.get("images") or {}).get("preview")},
    }
    validate_guide(guide)
    return guide


def build_site_data(
    project_root: Path,
    output_root: Path,
    *,
    selected_slugs: set[str] | None = None,
    copy_assets: bool = True,
) -> dict[str, Any]:
    current = read_json(project_root / "data" / "hero_onepager" / "current.json")
    snapshot_dir = project_root / current["path"]
    top20 = read_json(snapshot_dir / "top20.json")
    source = top20["source"]
    reviewed_dir = snapshot_dir / "reviewed"
    legacy_payload = read_json(project_root / "web" / "onepager-site" / "data" / "guides.json")
    legacy_by_slug = {row["slug"]: row for row in legacy_payload["guides"]}
    alias_config = read_json(ALIASES_PATH) if ALIASES_PATH.exists() else {}
    resources = ResourceCatalog(project_root, output_root, copy_assets)
    index_rows: list[dict[str, Any]] = []

    for path in sorted(reviewed_dir.glob("*.json")):
        reviewed = read_json(path)
        slug = reviewed["champion"]["slug"]
        if selected_slugs is not None and slug not in selected_slugs:
            continue
        legacy = legacy_by_slug.get(slug, {})
        champion_id = str(reviewed["champion"]["id"])
        guide = transform_guide(
            reviewed,
            source,
            legacy,
            alias_config.get(champion_id, []),
            resources,
        )
        write_json(output_root / "data" / "heroes" / f"{slug}.json", guide)
        index_rows.append({
            "id": guide["hero"]["id"],
            "slug": slug,
            "riotId": guide["hero"]["riotId"],
            "name": guide["hero"]["name"],
            "title": guide["hero"]["title"],
            "aliases": guide["hero"]["aliases"],
            "icon": guide["hero"]["icon"],
            "rank": guide["ranking"].get("rank"),
            "tier": guide["ranking"].get("tier"),
            "winRate": guide["ranking"].get("winRatePercent"),
            "pickRate": guide["ranking"].get("pickRatePercent"),
            "buildKey": guide["build"].get("key"),
            "buildName": guide["build"].get("name"),
            "status": "published",
            "legacyPoster": guide["legacy"].get("poster"),
        })

    index_rows.sort(key=lambda row: (row["rank"] is None, row["rank"] or 9999, row["id"]))
    payload = {
        "schemaVersion": 3,
        "site": {
            "title": "海斗一图流",
            "version": source["version"],
            "dataDate": source["dataDate"],
            "source": "ARAMKit",
            "guideCount": len(index_rows),
        },
        "guides": index_rows,
    }
    write_json(output_root / "data" / "index.json", payload)
    resources.write()
    return {"guideCount": len(index_rows), "version": source["version"], "dataDate": source["dataDate"]}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成模块化一图流网站数据")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=WORKTREE_ROOT)
    parser.add_argument("--no-copy-assets", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_site_data(
        args.project_root.resolve(),
        args.output_root.resolve(),
        copy_assets=not args.no_copy_assets,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
