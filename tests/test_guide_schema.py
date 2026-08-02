import copy
import unittest

from tools.guide_schema import ValidationError, validate_guide


def named_rows(prefix: str, count: int) -> list[dict]:
    return [{"id": index + 1, "name": f"{prefix}{index + 1}", "pickRate": 0.01} for index in range(count)]


def valid_fixture() -> dict:
    return {
        "schemaVersion": 2,
        "hero": {
            "id": 54,
            "slug": "malphite",
            "riotId": "Malphite",
            "name": "墨菲特",
            "title": "熔岩巨兽",
            "aliases": ["墨菲特", "熔岩巨兽", "Malphite", "石头", "石头人"],
            "icon": "assets/champions/malphite.webp",
        },
        "ranking": {"rank": 113, "tier": "B", "winRate": 0.473438, "pickRate": 0.097088},
        "build": {"key": "tank", "name": "坦克流"},
        "summonerSpells": named_rows("召唤师技能", 2),
        "skillOrder": "W>Q>E",
        "items": {
            "starter": named_rows("出门装", 2),
            "core": named_rows("核心装", 3),
            "recommended": named_rows("推荐装", 6),
        },
        "augments": {
            "prismatic": named_rows("棱彩", 6),
            "gold": named_rows("金色", 6),
            "silver": named_rows("银色", 6),
            "combinations": [
                {"ids": [index + 1, index + 11], "names": [f"组合{index + 1}A", f"组合{index + 1}B"]}
                for index in range(4)
            ],
        },
        "gameplay": {
            "status": "reviewed",
            "locked": True,
            "summary": ["先手开团。", "衔接控制。", "根据阵容调整装备。"],
        },
        "sources": [
            {
                "provider": "ARAMKit",
                "version": "16.15",
                "dataDate": "2026-08-01",
                "region": "unknown",
                "dataLevel": "aggregate",
            }
        ],
        "legacy": {"poster": "assets/guides/malphite-tank-648x1152.webp"},
    }


class GuideSchemaTests(unittest.TestCase):
    def test_valid_guide_passes(self):
        validate_guide(valid_fixture())

    def test_missing_six_items_fails(self):
        payload = valid_fixture()
        payload["items"]["recommended"] = payload["items"]["recommended"][:5]

        with self.assertRaisesRegex(ValidationError, "recommended"):
            validate_guide(payload)

    def test_each_augment_rarity_requires_six_entries(self):
        payload = valid_fixture()
        payload["augments"]["gold"] = payload["augments"]["gold"][:5]

        with self.assertRaisesRegex(ValidationError, "gold"):
            validate_guide(payload)

    def test_single_augment_pick_rate_must_be_at_least_one_percent(self):
        payload = valid_fixture()
        payload["augments"]["prismatic"][0]["pickRate"] = 0.0099

        with self.assertRaisesRegex(ValidationError, "pickRate"):
            validate_guide(payload)

    def test_numeric_display_names_are_rejected(self):
        payload = valid_fixture()
        payload["augments"]["silver"][0]["name"] = "123456"

        with self.assertRaisesRegex(ValidationError, "纯数字"):
            validate_guide(payload)

    def test_gameplay_must_remain_reviewed_and_locked(self):
        for field, invalid in (("locked", False), ("status", "auto-generated")):
            with self.subTest(field=field):
                payload = copy.deepcopy(valid_fixture())
                payload["gameplay"][field] = invalid
                with self.assertRaises(ValidationError):
                    validate_guide(payload)


if __name__ == "__main__":
    unittest.main()
