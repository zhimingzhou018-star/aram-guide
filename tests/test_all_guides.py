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

    def test_all_guides_publish_every_valid_build(self):
        build_count = 0
        invalid = []
        for slug, guide in self.guides.items():
            builds = guide.get("builds", [])
            build_count += len(builds)
            keys = [row.get("key") for row in builds]
            if not builds:
                invalid.append((slug, "count", len(builds)))
            if len(keys) != len(set(keys)):
                invalid.append((slug, "duplicate", keys))
            if guide.get("defaultBuildKey") != keys[0]:
                invalid.append((slug, "default", guide.get("defaultBuildKey"), keys))
            for build in builds:
                if not build["items"]["starter"]:
                    invalid.append((slug, build["key"], "starter"))
                if len(build["items"]["core"]) != 3 or len(build["items"]["recommended"]) != 6:
                    invalid.append((slug, build["key"], "items"))
        self.assertGreater(build_count, 172)
        self.assertEqual(invalid, [])

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

    def test_all_recommended_items_are_unique_and_linked_to_the_selected_route(self):
        invalid = []
        expected_sources = ["routeBoots", "routeLater", "routeLater"]
        for slug, guide in self.guides.items():
            for build in guide.get("builds", []):
                recommended = build["items"]["recommended"]
                ids = [row["id"] for row in recommended]
                if len(ids) != len(set(ids)):
                    invalid.append((slug, build["key"], "duplicate", ids))
                if [row.get("source") for row in recommended[3:]] != expected_sources:
                    invalid.append((slug, build["key"], "source"))
                for row in recommended[3:]:
                    if float(row.get("pickRate") or 0) < 0.01:
                        invalid.append((slug, build["key"], "pickRate", row["id"], row.get("pickRate")))

        self.assertEqual(invalid, [])

    def test_required_search_aliases_are_present(self):
        self.assertIn("石头", self.guides["malphite"]["hero"]["aliases"])
        self.assertIn("石头人", self.guides["malphite"]["hero"]["aliases"])
        self.assertIn("熊", self.guides["volibear"]["hero"]["aliases"])
        self.assertIn("狗熊", self.guides["volibear"]["hero"]["aliases"])
        self.assertIn("飞机", self.guides["corki"]["hero"]["aliases"])
        self.assertIn("人马", self.guides["hecarim"]["hero"]["aliases"])
        self.assertIn("火男", self.guides["brand"]["hero"]["aliases"])
        self.assertIn("huonan", self.guides["brand"]["hero"]["aliases"])
        self.assertIn("bulande", self.guides["brand"]["hero"]["aliases"])
        self.assertIn("jie", self.guides["zed"]["hero"]["aliases"])
        self.assertIn("腰子", self.guides["shen"]["hero"]["aliases"])
        self.assertIn("yaozi", self.guides["shen"]["hero"]["aliases"])
        self.assertIn("老头", self.guides["zilean"]["hero"]["aliases"])
        self.assertIn("时光老人", self.guides["zilean"]["hero"]["aliases"])
        self.assertIn("laotou", self.guides["zilean"]["hero"]["aliases"])
        self.assertIn("shiguanglaoren", self.guides["zilean"]["hero"]["aliases"])
        self.assertIn("狼人", self.guides["warwick"]["hero"]["aliases"])
        self.assertIn("武器大师", self.guides["jax"]["hero"]["aliases"])
        self.assertIn("萧炎", self.guides["udyr"]["hero"]["aliases"])
        self.assertIn("瑞文", self.guides["riven"]["hero"]["aliases"])
        self.assertIn("酸辣粉", self.guides["seraphine"]["hero"]["aliases"])
        self.assertIn("金克斯", self.guides["jinx"]["hero"]["aliases"])
        self.assertIn("挖掘机", self.guides["reksai"]["hero"]["aliases"])
        self.assertNotIn("挖掘机", self.guides["renekton"]["hero"]["aliases"])

    def test_high_frequency_no_result_searches_have_alias_mappings(self):
        expected = {
            "brand": ["火男", "huo"],
            "shyvana": ["龙女", "long"],
            "vladimir": ["吸血鬼", "吸血"],
            "mordekaiser": ["铁男"],
            "fiddlesticks": ["稻草人"],
            "monkeyking": ["猴", "猴子"],
            "fizz": ["小鱼", "小鱼人", "鱼"],
            "masteryi": ["jiansheng"],
            "hecarim": ["renma"],
            "tahmkench": ["tamu"],
        }
        for slug, aliases in expected.items():
            with self.subTest(slug=slug):
                for alias in aliases:
                    self.assertIn(alias, self.guides[slug]["hero"]["aliases"])

    def test_home_index_stays_lightweight(self):
        self.assertLess((ROOT / "data" / "index.json").stat().st_size, 120_000)
        for row in self.index["guides"]:
            self.assertNotIn("items", row)
            self.assertNotIn("augments", row)
            self.assertNotIn("gameplay", row)


if __name__ == "__main__":
    unittest.main()
