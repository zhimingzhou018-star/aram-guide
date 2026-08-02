import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ServiceWorkerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worker = (ROOT / "sw.js").read_text(encoding="utf-8")
        cls.app = (ROOT / "app.js").read_text(encoding="utf-8")

    def test_navigation_and_index_use_network_first(self):
        self.assertIn("networkFirst", self.worker)
        self.assertRegex(self.worker, r'request\.mode === "navigate"[\s\S]*networkFirst')
        self.assertRegex(self.worker, r'data/index\.json[\s\S]*networkFirst')

    def test_hero_json_uses_stale_while_revalidate(self):
        self.assertIn("staleWhileRevalidate", self.worker)
        self.assertRegex(self.worker, r'data/heroes/[\s\S]*staleWhileRevalidate')

    def test_shared_icons_and_legacy_posters_use_cache_first(self):
        self.assertRegex(self.worker, r'assets/resources/[\s\S]*cacheFirst')
        self.assertRegex(self.worker, r'assets/guides/[\s\S]*cacheFirst')

    def test_version_change_deletes_old_caches(self):
        self.assertRegex(self.worker, r'CACHE_PREFIX\s*=\s*"aram-guide-v10"')
        self.assertIn("caches.delete", self.worker)

    def test_invalid_detail_data_has_legacy_poster_fallback(self):
        self.assertIn("Invalid hero guide payload", self.app)
        self.assertIn("LegacyPosterFallback(indexGuide)", self.app)
        self.assertIn("模块数据暂不可用", self.app)


if __name__ == "__main__":
    unittest.main()
