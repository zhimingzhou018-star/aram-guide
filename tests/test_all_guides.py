import json
import unittest
from pathlib import Path

from tools.guide_schema import validate_guide


ROOT = Path(__file__).resolve().parents[1]


class AllGuidesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = json.loads((ROOT / "data" / "index.json").read_text(encoding="utf-8"))
        cls.guides = {
            path.stem: json.loads(path.read_text(encoding="utf-8"))
            for path in (ROOT / "data" / "heroes").glob("*.json")
        }

    def test_all_172_guides_validate(self):
        self.assertEqual(len(self.index["guides"]), 172)
        self.assertEqual(len(self.guides), 172)
        for guide in self.guides.values():
            validate_guide(guide)

    def test_all_referenced_assets_exist(self):
        missing = []
        for slug, guide in self.guides.items():
            references = [guide["hero"]["icon"], guide["legacy"]["poster"]]
            references += [row["icon"] for row in guide["hero"]["abilities"]]
            references += [row["icon"] for row in guide["summonerSpells"]]
            for group in guide["items"].values():
                references += [row["icon"] for row in group]
            for rarity in ("prismatic", "gold", "silver"):
                references += [row["icon"] for row in guide["augments"][rarity]]
            references += [
                f"assets/resources/augments/{augment_id}.webp"
                for combination in guide["augments"]["combinations"]
                for augment_id in combination["ids"]
            ]
            missing += [(slug, reference) for reference in references if not (ROOT / reference).exists()]
        self.assertEqual(missing, [])

    def test_all_editorial_gameplay_is_locked(self):
        unlocked = [slug for slug, guide in self.guides.items() if not guide["gameplay"].get("locked")]
        self.assertEqual(unlocked, [])

    def test_all_single_augments_meet_one_percent_pick_rate(self):
        invalid = []
        for slug, guide in self.guides.items():
            for rarity in ("prismatic", "gold", "silver"):
                invalid += [
                    (slug, rarity, row["id"], row.get("pickRate"))
                    for row in guide["augments"][rarity]
                    if float(row.get("pickRate") or 0) < 0.01
                ]
        self.assertEqual(invalid, [])

    def test_required_search_aliases_are_present(self):
        self.assertIn("石头", self.guides["malphite"]["hero"]["aliases"])
        self.assertIn("石头人", self.guides["malphite"]["hero"]["aliases"])
        self.assertIn("熊", self.guides["volibear"]["hero"]["aliases"])
        self.assertIn("狗熊", self.guides["volibear"]["hero"]["aliases"])
        self.assertIn("飞机", self.guides["corki"]["hero"]["aliases"])

    def test_home_index_stays_lightweight(self):
        self.assertLess((ROOT / "data" / "index.json").stat().st_size, 120_000)
        for row in self.index["guides"]:
            self.assertNotIn("items", row)
            self.assertNotIn("augments", row)
            self.assertNotIn("gameplay", row)


if __name__ == "__main__":
    unittest.main()
