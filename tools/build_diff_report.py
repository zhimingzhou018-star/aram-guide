"""Build a human-review diff between published modules and a raw candidate snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def top_ids(
    rows: list[dict[str, Any]],
    limit: int = 6,
    min_samples: int = 100,
    min_pick_rate: float = 0,
) -> list[int]:
    eligible = [
        row for row in rows
        if int(row.get("sampleCount", 0)) >= min_samples
        and float(row.get("pickRate") or 0) >= min_pick_rate
    ]
    eligible.sort(key=lambda row: (float(row.get("winRate", 0)), int(row.get("sampleCount", 0))), reverse=True)
    return [int(row["id"]) for row in eligible[:limit]]


def top_build(details: dict[str, Any], min_samples: int = 100) -> str | None:
    rows = [
        row for row in details.get("builds", {}).get("archetypes", [])
        if int(row.get("sampleCount", 0)) >= min_samples
    ]
    if not rows:
        return None
    return max(rows, key=lambda row: (float(row.get("winRate", 0)), int(row.get("sampleCount", 0)))).get("key")


def build_diff_report(
    current_guides: list[dict[str, Any]],
    raw: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    ranking_by_id = {int(row["id"]): row for row in raw.get("rankings", {}).get("rows", [])}
    details_by_id = {int(key): value for key, value in raw.get("details", {}).items()}
    augment_resources = raw.get("augmentResources", {})
    heroes = []
    for guide in current_guides:
        hero_id = int(guide["hero"]["id"])
        ranking = ranking_by_id.get(hero_id, {})
        details = details_by_id.get(hero_id, {})
        candidate_augments: dict[str, list[int]] = {}
        all_augments = details.get("augments", {}).get("all", [])
        for rarity in ("prismatic", "gold", "silver"):
            rows = [
                row for row in all_augments
                if augment_resources.get(str(row.get("id")), {}).get("rarity") == rarity
            ]
            candidate_augments[rarity] = top_ids(rows, min_pick_rate=0.01)

        current_items = [int(row["id"]) for row in guide.get("items", {}).get("recommended", [])]
        candidate_items = top_ids(details.get("items", {}).get("all", []))
        current_augments = {
            rarity: [int(row["id"]) for row in guide.get("augments", {}).get(rarity, [])]
            for rarity in ("prismatic", "gold", "silver")
        }
        gameplay = guide.get("gameplay", {})
        current_rank = guide.get("ranking", {}).get("rank")
        current_win = guide.get("ranking", {}).get("winRate")
        candidate_win = ranking.get("winRate")
        hero_report = {
            "id": hero_id,
            "slug": guide["hero"]["slug"],
            "name": guide["hero"].get("name"),
            "ranking": {
                "before": current_rank,
                "after": ranking.get("rank"),
                "winRateBefore": current_win,
                "winRateAfter": candidate_win,
                "winRateDelta": None if current_win is None or candidate_win is None else round(float(candidate_win) - float(current_win), 6),
            },
            "build": {"before": guide.get("build", {}).get("key"), "after": top_build(details)},
            "items": {"before": current_items, "candidateTop": candidate_items},
            "augments": {"before": current_augments, "candidateTop": candidate_augments},
            "lowSampleWarnings": {
                "itemsExcluded": sum(int(row.get("sampleCount", 0)) < 100 for row in details.get("items", {}).get("all", [])),
                "augmentsExcluded": 0,
                "augmentsBelowOnePercentExcluded": sum(float(row.get("pickRate") or 0) < 0.01 for row in all_augments),
            },
            "lockedGameplay": {
                "locked": bool(gameplay.get("locked")),
                "preserved": True,
                "checksum": stable_hash(gameplay.get("summary", [])),
            },
        }
        hero_report["changed"] = any((
            hero_report["ranking"]["before"] != hero_report["ranking"]["after"],
            hero_report["build"]["before"] != hero_report["build"]["after"],
            current_items != candidate_items,
            current_augments != candidate_augments,
        ))
        heroes.append(hero_report)

    return {
        "source": {
            "provider": "ARAMKit",
            "region": "unknown",
            "dataLevel": "aggregate",
            "segment": "all",
            "version": metadata.get("version"),
            "dataDate": metadata.get("dataDate"),
        },
        "summary": {
            "heroCount": len(heroes),
            "changedHeroCount": sum(hero["changed"] for hero in heroes),
            "lockedGameplayCount": sum(hero["lockedGameplay"]["locked"] for hero in heroes),
        },
        "reviewGate": {
            "manualApprovalRequired": True,
            "publishAllowed": False,
            "reason": "候选数据仅供审核，禁止自动覆盖生产数据。",
        },
        "heroes": heroes,
    }


def load_raw(raw_dir: Path) -> dict[str, Any]:
    rankings = json.loads((raw_dir / "champion-rankings.json").read_text(encoding="utf-8"))
    augments = json.loads((raw_dir / "augments.json").read_text(encoding="utf-8"))
    details = {
        int(path.stem): json.loads(path.read_text(encoding="utf-8"))
        for path in (raw_dir / "champion-details").glob("*.json")
    }
    return {"rankings": rankings, "details": details, "augmentResources": augments}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-guides", type=Path, default=Path("data/heroes"))
    parser.add_argument("--candidate", type=Path, required=True, help="Candidate snapshot directory")
    parser.add_argument("--output", type=Path, default=Path("reports/update-diff.json"))
    args = parser.parse_args()
    current = [json.loads(path.read_text(encoding="utf-8")) for path in args.current_guides.glob("*.json")]
    metadata = json.loads((args.candidate / "manifest.json").read_text(encoding="utf-8"))
    report = build_diff_report(current, load_raw(args.candidate / "raw"), metadata)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
