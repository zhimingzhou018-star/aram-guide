import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.release_guard import ReleaseGateError, verify_production_release


class ReleaseGuardTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.remote = base / "remote.git"
        self.repo = base / "site"
        self.run_cmd(base, "git", "init", "--bare", str(self.remote))
        self.run_cmd(base, "git", "init", "-b", "main", str(self.repo))
        self.run_cmd(self.repo, "git", "config", "user.name", "Test User")
        self.run_cmd(self.repo, "git", "config", "user.email", "test@example.com")
        self.run_cmd(self.repo, "git", "commit", "--allow-empty", "-m", "Root")
        (self.repo / "index.html").write_text("ok", encoding="utf-8")
        self.run_cmd(self.repo, "git", "add", "index.html")
        self.run_cmd(self.repo, "git", "commit", "-m", "Initial")
        self.run_cmd(self.repo, "git", "remote", "add", "origin", str(self.remote))
        self.run_cmd(self.repo, "git", "push", "-u", "origin", "main")
        self.head = self.output(self.repo, "git", "rev-parse", "HEAD")
        self.release_tag = "release-test"
        self.run_cmd(self.repo, "git", "tag", "-a", self.release_tag, "-m", "Test release")
        self.run_cmd(self.repo, "git", "push", "origin", self.release_tag)

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def run_cmd(cwd: Path, *command: str) -> None:
        subprocess.run(command, cwd=cwd, check=True, capture_output=True)

    @staticmethod
    def output(cwd: Path, *command: str) -> str:
        return subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()

    def test_accepts_clean_approved_remote_main(self):
        result = verify_production_release(self.repo, self.head, self.release_tag)
        self.assertEqual(result["commit"], self.head)
        self.assertEqual(result["tag"], self.release_tag)

    def test_rejects_dirty_worktree(self):
        (self.repo / "index.html").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ReleaseGateError, "工作区不干净"):
            verify_production_release(self.repo, self.head, self.release_tag)

    def test_rejects_unapproved_commit(self):
        with self.assertRaisesRegex(ReleaseGateError, "验收提交不是当前 HEAD"):
            verify_production_release(self.repo, f"{self.head}^", self.release_tag)

    def test_rejects_non_main_branch(self):
        self.run_cmd(self.repo, "git", "switch", "-c", "feature")
        with self.assertRaisesRegex(ReleaseGateError, "只允许从 main"):
            verify_production_release(self.repo, self.head, self.release_tag)

    def test_rejects_unpublished_release_tag(self):
        self.run_cmd(self.repo, "git", "tag", "local-only")
        with self.assertRaisesRegex(ReleaseGateError, "版本标签尚未推送"):
            verify_production_release(self.repo, self.head, "local-only")


if __name__ == "__main__":
    unittest.main()
