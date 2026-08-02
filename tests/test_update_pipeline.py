import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from tools.build_diff_report import build_diff_report
from tools.check_aramkit_update import TerminalHttpError, check_for_update, fetch_url
from tools.fetch_aramkit_snapshot import SnapshotError, fetch_snapshot


class UpdatePipelineTests(unittest.TestCase):
    def test_workflow_is_review_only_and_never_pushes_main(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "check-data-update.yml").read_text(encoding="utf-8")
        self.assertIn("schedule:", workflow)
        self.assertIn("upload-artifact", workflow)
        self.assertNotIn("git push", workflow)
        self.assertNotIn("contents: write", workflow)

    def test_same_data_date_makes_zero_detail_requests(self):
        detail_calls = []
        result = check_for_update(
            {"version": "16.15", "dataDate": "2026-08-01"},
            lambda: {"version": "16.15", "dataDate": "2026-08-01"},
            detail_fetch=lambda *_: detail_calls.append("called"),
        )
        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(detail_calls, [])

    def test_429_stops_without_retry_storm(self):
        calls = []

        def opener(request, timeout=30):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url, 429, "rate limited", {}, None)

        with self.assertRaises(TerminalHttpError):
            fetch_url("https://example.test/version", opener=opener, sleep=lambda _: None)
        self.assertEqual(len(calls), 1)

    def test_invalid_hero_keeps_current_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "current.json"
            current.write_text('{"snapshot":"old"}', encoding="utf-8")

            responses = {
                "champions.json": {"1": {"id": 1}},
                "items.json": {},
                "augments.json": {},
                "summoner-spells.json": {},
                "champion-rankings.json": {"rows": [{"id": 1}]},
                "champion-details/1.json": {"champion": {"id": 999}},
            }

            def fake_fetch(url):
                return next(value for suffix, value in responses.items() if url.endswith(suffix))

            with self.assertRaises(SnapshotError):
                fetch_snapshot(
                    {
                        "endpoint": "https://data.test",
                        "resourcePath": "resources-v1",
                        "dataPath": "data-v1",
                        "version": "16.16",
                        "dataDate": "2026-08-02",
                    },
                    root / "snapshots",
                    current_manifest=current,
                    fetch_json=fake_fetch,
                    sleep=lambda _: None,
                )
            self.assertEqual(json.loads(current.read_text(encoding="utf-8"))["snapshot"], "old")
            self.assertFalse((root / "snapshots" / "16.16-20260802").exists())

    def test_locked_gameplay_is_preserved_in_review_gate(self):
        current = {
            "hero": {"id": 1, "slug": "hero"},
            "ranking": {"rank": 1, "winRate": 0.5},
            "build": {"key": "crit"},
            "items": {"recommended": [{"id": value} for value in range(1, 7)]},
            "augments": {"prismatic": [], "gold": [], "silver": []},
            "gameplay": {"locked": True, "summary": ["人工审核玩法"]},
        }
        raw = {
            "rankings": {"rows": [{"id": 1, "rank": 2, "winRate": 0.51}]},
            "details": {1: {"champion": {"id": 1}, "builds": {"archetypes": []}, "items": {"all": []}, "augments": {"all": []}}},
            "augmentResources": {},
        }
        report = build_diff_report([current], raw, {"version": "16.16", "dataDate": "2026-08-02"})
        gate = report["heroes"][0]["lockedGameplay"]
        self.assertTrue(gate["preserved"])
        self.assertTrue(gate["locked"])
        self.assertTrue(report["reviewGate"]["manualApprovalRequired"])
        self.assertFalse(report["reviewGate"]["publishAllowed"])

    def test_diff_candidates_exclude_augments_below_one_percent_pick_rate(self):
        current = {
            "hero": {"id": 1, "slug": "hero"},
            "ranking": {},
            "build": {},
            "items": {"recommended": []},
            "augments": {"prismatic": [], "gold": [], "silver": []},
            "gameplay": {"locked": True, "summary": []},
        }
        rows = [
            {"id": 1, "sampleCount": 10_000, "pickRate": 0.0099, "winRate": 0.99},
            {"id": 2, "sampleCount": 10_000, "pickRate": 0.01, "winRate": 0.60},
        ]
        raw = {
            "rankings": {"rows": [{"id": 1}]},
            "details": {1: {"augments": {"all": rows}}},
            "augmentResources": {"1": {"rarity": "prismatic"}, "2": {"rarity": "prismatic"}},
        }

        report = build_diff_report([current], raw, {})

        self.assertEqual(report["heroes"][0]["augments"]["candidateTop"]["prismatic"], [2])


if __name__ == "__main__":
    unittest.main()
