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


if __name__ == "__main__":
    unittest.main()
