import json
import tempfile
import unittest
from pathlib import Path

from tools.build_modular_data import build_site_data
from tools.guide_schema import validate_guide


PROJECT_ROOT = Path(__file__).resolve().parents[4]


class BuildModularDataTests(unittest.TestCase):
    def test_representative_heroes_are_transformed_and_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            result = build_site_data(
                PROJECT_ROOT,
                output_root,
                selected_slugs={"malphite", "volibear", "graves"},
                copy_assets=False,
            )

            self.assertEqual(result["guideCount"], 3)
            guides = {
                slug: json.loads((output_root / "data" / "heroes" / f"{slug}.json").read_text(encoding="utf-8"))
                for slug in ("malphite", "volibear", "graves")
            }
            for guide in guides.values():
                validate_guide(guide)

            self.assertIn("石头", guides["malphite"]["hero"]["aliases"])
            self.assertIn("石头人", guides["malphite"]["hero"]["aliases"])
            self.assertIn("熊", guides["volibear"]["hero"]["aliases"])
            self.assertIn("狗熊", guides["volibear"]["hero"]["aliases"])
            self.assertEqual(len(guides["graves"]["items"]["recommended"]), 6)
            self.assertTrue(guides["graves"]["gameplay"]["locked"])
            self.assertGreaterEqual(len(guides["malphite"]["builds"]), 2)
            self.assertEqual(guides["malphite"]["defaultBuildKey"], guides["malphite"]["builds"][0]["key"])
            self.assertNotEqual(
                guides["malphite"]["builds"][0]["items"]["core"],
                guides["malphite"]["builds"][1]["items"]["core"],
            )

    def test_index_is_lightweight_and_excludes_detail_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            build_site_data(
                PROJECT_ROOT,
                output_root,
                selected_slugs={"malphite"},
                copy_assets=False,
            )
            payload = json.loads((output_root / "data" / "index.json").read_text(encoding="utf-8"))
            hero = payload["guides"][0]

            self.assertEqual(hero["slug"], "malphite")
            self.assertNotIn("items", hero)
            self.assertNotIn("augments", hero)
            self.assertNotIn("gameplay", hero)

    def test_combination_only_augments_are_added_to_resource_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            build_site_data(
                PROJECT_ROOT,
                output_root,
                selected_slugs={"lux"},
                copy_assets=False,
            )
            guide = json.loads((output_root / "data" / "heroes" / "lux.json").read_text(encoding="utf-8"))
            catalog = json.loads((output_root / "data" / "resources" / "augments.json").read_text(encoding="utf-8"))
            combination_ids = {
                str(augment_id)
                for combination in guide["augments"]["combinations"]
                for augment_id in combination["ids"]
            }

            self.assertTrue(combination_ids.issubset(catalog))

    def test_100_sample_floor_keeps_bard_on_high_segment(self):
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            build_site_data(
                PROJECT_ROOT,
                output_root,
                selected_slugs={"bard"},
                copy_assets=False,
            )
            guide = json.loads((output_root / "data" / "heroes" / "bard.json").read_text(encoding="utf-8"))
            aramkit = next(source for source in guide["sources"] if source["provider"] == "ARAMKit")

            self.assertEqual(aramkit["segment"], "high")
            self.assertIsNone(aramkit.get("fallbackReason"))


if __name__ == "__main__":
    unittest.main()
