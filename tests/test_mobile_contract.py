import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MobileContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = (ROOT / "styles.css").read_text(encoding="utf-8")
        cls.app = (ROOT / "app.js").read_text(encoding="utf-8")

    def test_page_prevents_horizontal_overflow(self):
        self.assertIn("overflow-x: hidden", self.css)
        self.assertIn("min-width: 320px", self.css)

    def test_home_is_two_columns_and_detail_items_are_three_by_two(self):
        self.assertRegex(
            self.css,
            r"\.guide-list\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)",
        )
        self.assertRegex(
            self.css,
            r"\.item-grid\s*\{[^}]*grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)",
        )

    def test_each_augment_tier_is_three_by_two_with_readable_icons(self):
        self.assertRegex(
            self.css,
            r"\.augment-tier ul\s*\{[^}]*grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)",
        )
        self.assertRegex(self.css, r"\.augment-tier \.icon-tile img\s*\{[^}]*width:\s*4[4-9]px")
        self.assertRegex(self.css, r"\.augment-tier \.icon-tile span\s*\{[^}]*font-size:\s*10px")

    def test_detail_resources_are_lazy_loaded_and_dimensioned(self):
        self.assertIn('loading="lazy"', self.app)
        self.assertIn('decoding="async"', self.app)
        self.assertRegex(self.app, r'width="(4[4-9]|5[0-9]|6[0-9]|7[0-9])"')


if __name__ == "__main__":
    unittest.main()
